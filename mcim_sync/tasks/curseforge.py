from concurrent.futures import as_completed

from mcim_sync.utils.loger import log
from mcim_sync.utils.constans import Platform
from mcim_sync.utils.telegram import (
    QueueSyncNotification,
    SearchSyncNotification,
    RefreshNotification,
    CategoriesNotification,
)
from mcim_sync.config import Config
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

    curseforge_pool, curseforge_futures = create_tasks_pool(
        sync_mod,  # 需要 ProjectDetail 返回值
        curseforge_expired_modids,
        MAX_WORKERS,
        "refresh_curseforge",
    )
    projects_detail_info = []
    for future in as_completed(curseforge_futures):
        result = future.result()
        if result:
            projects_detail_info.append(result)
    else:
        curseforge_pool.shutdown()

    failed_count = len(curseforge_expired_modids) - len(projects_detail_info)
    failed_modids = [
        modid
        for modid in curseforge_expired_modids
        if modid not in projects_detail_info
    ]
    log.info(
        f"CurseForge expired data sync finished, total: {len(curseforge_expired_modids)}, "
        f"success: {len(projects_detail_info)}, failed: {failed_count}, "
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

    if modids:
        # pool, futures = create_tasks_pool(sync_mod, modids, MAX_WORKERS, "curseforge")
        pool, futures = create_tasks_pool(
            sync_mod, new_modids, MAX_WORKERS, "sync_curseforge"
        )  # https://github.com/mcmod-info-mirror/mcim-sync/issues/2

        projects_detail_info = []
        for future in as_completed(futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

        pool.shutdown()
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


def refresh_curseforge_categories() -> bool:
    log.info("Start fetching curseforge categories.")
    result = sync_categories(gameId=432)
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


def sync_curseforge_by_search():
    """
    从搜索接口拉取 curseforge 的新 Mod

    ?gameId=432&classId=6&sortField=11&sortOrder=desc
    """
    log.info("Start fetching new curseforge mod by search.")

    # /v1/categories?gameId=432&classOnly=true
    # 排除 Bukkit Plugins
    class_info = [
        {"id": 4546, "name": "Customization"},
        {"id": 4559, "name": "Addons"},
        {"id": 12, "name": "Resource Packs"},
        {"id": 6, "name": "Mods"},
        {"id": 4471, "name": "Modpacks"},
        {"id": 17, "name": "Worlds"},
        {"id": 6552, "name": "Shaders"},
        {"id": 6945, "name": "Data Packs"},
    ]
    classIds = [cls["id"] for cls in class_info]
    new_modids = []

    for classId in classIds:
        class_name = class_info[classIds.index(classId)]["name"]
        log.info(
            f"Fetching new curseforge mod by search, classId: {classId}, name: {class_name}"
        )
        result = check_newest_search_result(classId=classId)
        new_modids.extend(result)
        log.info(
            f"New modids fetched for classId {classId} name {class_name}: {len(result)}"
        )

    new_modids = list(set(new_modids))  # 去重

    log.info(f"CurseForge new modids fetched: {len(new_modids)}")
    if new_modids:
        pool, futures = create_tasks_pool(
            sync_mod, new_modids, MAX_WORKERS, "sync_curseforge_by_search"
        )

        projects_detail_info = []
        for future in as_completed(futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

        pool.shutdown()
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

    curseforge_pool, curseforge_futures = create_tasks_pool(
        sync_mod, curseforge_data, MAX_WORKERS, "curseforge"
    )

    log.info(
        f"All {len(curseforge_futures)} tasks submitted, waiting for completion..."
    )

    projects_detail_info = []
    for future in as_completed(curseforge_futures):
        result = future.result()
        if result:
            projects_detail_info.append(result)
    else:
        curseforge_pool.shutdown()

    failed_count = len(curseforge_data) - len(projects_detail_info)
    failed_modids = [
        modid for modid in curseforge_data if modid not in projects_detail_info
    ]

    log.info(
        f"CurseForge full sync finished, total: {len(curseforge_data)}, "
        f"success: {len(projects_detail_info)}, failed: {failed_count}, "
        f"failed modids: {failed_modids if failed_modids else 'None'}"
    )

    curseforge_pool.shutdown()
