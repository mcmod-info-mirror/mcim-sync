from concurrent.futures import as_completed
from typing import List, Optional

from mcim_sync.utils.loger import log
from mcim_sync.utils.constants import Platform
from mcim_sync.utils.telegram import (
    QueueSyncNotification,
    SearchSyncNotification,
    RefreshNotification,
    CategoriesNotification,
)
from mcim_sync.config import Config
from mcim_sync.models import ProjectDetail
from mcim_sync.utils.constants import GAME_432_CLASSES_INFO
from mcim_sync.sync.curseforge import sync_mod, sync_categories
from mcim_sync.checker.curseforge import (
    check_curseforge_modids_available,
    check_curseforge_fileids_available,
    check_curseforge_fingerprints_available,
    check_new_modids,
    check_newest_search_result,
)
from mcim_sync.fetcher.curseforge import (
    fetch_expired_curseforge_data,
    fetch_all_curseforge_data,
)
from mcim_sync.queues.curseforge import clear_curseforge_all_queues
from mcim_sync.tasks import create_tasks_pool

config = Config.load()


MAX_WORKERS: int = config.max_workers


def refresh_curseforge_with_modify_date() -> bool:
    log.info("Start fetching expired CurseForge data.")

    curseforge_expired_modids = fetch_expired_curseforge_data()

    # 到底哪来的的 wow，排除小于 30000 的 modid
    curseforge_expired_modids = [
        modid for modid in curseforge_expired_modids if modid >= 30000
    ]

    log.info(f"Curseforge expired data fetched: {len(curseforge_expired_modids)}")
    log.info("Start syncing CurseForge expired data...")

    with create_tasks_pool(
        sync_mod,
        curseforge_expired_modids,
        MAX_WORKERS,
        "refresh_curseforge",
    ) as curseforge_futures:
        projects_detail_info: List[ProjectDetail] = []
        for future in as_completed(curseforge_futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

    success_modids = [project.id for project in projects_detail_info if project]

    failed_count = len(curseforge_expired_modids) - len(success_modids)
    failed_modids = [
        modid for modid in curseforge_expired_modids if modid not in success_modids
    ]

    log.info(
        f"CurseForge expired data sync finished, total: {len(curseforge_expired_modids)}, "
        f"success: {len(success_modids)}, failed: {failed_count}, "
        f"failed modids: {failed_modids if failed_modids else 'None'}"
    )

    if config.telegram_bot:
        notification = RefreshNotification(
            platform=Platform.CURSEFORGE,
            projects_detail_info=projects_detail_info,
            failed_count=failed_count,
        )
        notification.send_to_telegram()
        log.info("CurseForge refresh message sent to telegram.")

    return True


def fetch_curseforge_not_found_ids_from_queue():
    modids = []
    avaliable_modids = check_curseforge_modids_available()
    modids.extend(avaliable_modids)
    log.info(f"CurseForge modids queue available modids: {len(avaliable_modids)}")
    avaliable_modids = check_curseforge_fileids_available()
    modids.extend(avaliable_modids)
    log.info(f"CurseForge fileids queue available modids: {len(avaliable_modids)}")
    avaliable_modids = check_curseforge_fingerprints_available()
    modids.extend(avaliable_modids)
    log.info(f"CurseForge fingerprints queue available modids: {len(avaliable_modids)}")

    modids = [modid for modid in modids if modid >= 30000]  # 排除掉 0-30000 的 modid
    return modids


def sync_curseforge_queue() -> bool:
    log.info("Start fetching curseforge queue.")

    modids = fetch_curseforge_not_found_ids_from_queue()

    # 检查这些 modid 是否是新的
    new_modids = check_new_modids(modids=modids)
    log.info(f"New modids: {new_modids}, count: {len(new_modids)}")

    if new_modids:
        with create_tasks_pool(
            sync_mod, new_modids, MAX_WORKERS, "sync_curseforge_queue"
        ) as futures:
            projects_detail_info = []
            for future in as_completed(futures):
                result = future.result()
                if result:
                    projects_detail_info.append(result)

        log.info(f"CurseForge queue sync finished, total: {len(modids)}")

        # clear queue
        clear_curseforge_all_queues()
        log.info("CurseForge queue cleared.")

        if config.telegram_bot:
            notice = QueueSyncNotification(
                platform=Platform.CURSEFORGE,
                projects_detail_info=projects_detail_info,
                total_catached_count=len(modids),
            )

            notice.send_to_telegram()

            log.info("All Message sent to telegram.")

    return True


def refresh_curseforge_categories(gameId: int = 432) -> bool:
    log.info(f"Start fetching curseforge categories. (gameId: {gameId})")
    result = sync_categories(gameId=gameId)
    total_catached_count = len(result)
    log.info(
        f"CurseForge categories sync finished, total categories: {total_catached_count}"
    )

    if config.telegram_bot:
        CategoriesNotification(
            total_catached_count=total_catached_count
        ).send_to_telegram()
        log.info("All Message sent to telegram.")

    return True


def sync_curseforge_by_search(gameId: int = 432, classes_info: Optional[List[dict]] = GAME_432_CLASSES_INFO) -> bool:
    """
    从搜索接口拉取 curseforge 的新 Mod

    ?gameId=432&classId=6&sortField=11&sortOrder=desc
    """
    log.info(f"Start fetching new curseforge mod by search. (gameId: {gameId})")
    new_modids = []

    for class_info in classes_info:
        classId = class_info["id"]
        class_name = class_info["name"]
        log.info(
            f"Fetching new curseforge mod by search, classId: {classId}, name: {class_name}"
        )
        result = check_newest_search_result(gameId=gameId, classId=classId)
        new_modids.extend(result)
        log.info(
            f"New modids fetched for classId {classId} name {class_name}: {len(result)}"
        )

    new_modids = list(set(new_modids))  # 去重

    log.info(f"CurseForge new modids fetched: {len(new_modids)}")
    if new_modids:
        with create_tasks_pool(
            sync_mod, new_modids, MAX_WORKERS, "sync_curseforge_by_search"
        ) as futures:
            projects_detail_info = []
            for future in as_completed(futures):
                result = future.result()
                if result:
                    projects_detail_info.append(result)

        log.info(f"CurseForge search sync finished, total: {len(new_modids)}")

        if config.telegram_bot:
            notice = SearchSyncNotification(
                platform=Platform.CURSEFORGE,
                projects_detail_info=projects_detail_info,
                total_catached_count=len(new_modids),
            )
            notice.send_to_telegram()

            log.info("All Message sent to telegram.")

    return True


def sync_curseforge_full():
    log.info("Start fetching curseforge all data.")

    curseforge_data = fetch_all_curseforge_data()
    log.info(f"Curseforge data totally fetched: {len(curseforge_data)}")

    with create_tasks_pool(
        sync_mod, curseforge_data, MAX_WORKERS, "curseforge_refresh_full"
    ) as curseforge_futures:
        log.info(
            f"All {len(curseforge_futures)} tasks submitted, waiting for completion..."
        )

        projects_detail_info: List[ProjectDetail] = []
        for future in as_completed(curseforge_futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

    success_modids = [project.id for project in projects_detail_info if project]

    failed_count = len(curseforge_data) - len(success_modids)
    failed_modids = [modid for modid in curseforge_data if modid not in success_modids]

    log.info(
        f"CurseForge full sync finished, total: {len(curseforge_data)}, "
        f"success: {len(success_modids)}, failed: {failed_count}, "
        f"failed modids: {failed_modids if failed_modids else 'None'}"
    )

    if config.telegram_bot:
        notification = RefreshNotification(
            platform=Platform.CURSEFORGE,
            projects_detail_info=projects_detail_info,
            failed_count=failed_count,
        )
        notification.send_to_telegram()
        log.info("CurseForge refresh message sent to telegram.")

    return True
