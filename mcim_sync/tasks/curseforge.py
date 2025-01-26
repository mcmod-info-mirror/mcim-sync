import threading

from concurrent.futures import ThreadPoolExecutor, as_completed

from mcim_sync.utils.loger import log
from mcim_sync.utils.telegram import (
    SyncNotification,
    RefreshNotification,
)
from mcim_sync.config import Config
from mcim_sync.sync.curseforge import sync_mod, sync_categories
from mcim_sync.checker.curseforge import (
    check_curseforge_modids_available,
    check_curseforge_fileids_available,
    check_curseforge_fingerprints_available,
    check_new_modids,
)
from mcim_sync.fetcher.curseforge import fetch_expired_curseforge_data
from mcim_sync.queues.curseforge import clear_curseforge_all_queues
from mcim_sync.tasks import create_tasks_pool, curseforge_pause_event

config = Config.load()


MAX_WORKERS: int = config.max_workers


def refresh_curseforge_with_modify_date() -> bool:
    log.info("Start fetching expired CurseForge data.")

    if config.sync_curseforge:
        curseforge_expired_modids = fetch_expired_curseforge_data()

        log.info(f"Curseforge expired data fetched: {len(curseforge_expired_modids)}")
        log.info(f"Start syncing CurseForge expired data...")

        curseforge_pause_event.set()
        curseforge_pool, curseforge_futures = create_tasks_pool(
            sync_mod,  # 需要 ProjectDetail 返回值
            curseforge_expired_modids,
            MAX_WORKERS,
            "curseforge",
        )
        projects_detail_info = []
        for future in as_completed(curseforge_futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)
        else:
            curseforge_pool.shutdown()

        if config.telegram_bot:
            notification = RefreshNotification(
                platform="Curseforge",
                projects_detail_info=projects_detail_info,
            )
            notification.send_to_telegram()
            log.info("CurseForge refresh message sent to telegram.")

    return True


def fetch_curseforge_fileids_from_queue():
    modids = []
    avaliable_modids = check_curseforge_modids_available()
    modids.extend(avaliable_modids)
    log.info(f"CurseForge modids available: {len(avaliable_modids)}")
    avaliable_fileids = check_curseforge_fileids_available()
    modids.extend(avaliable_fileids)
    log.info(f"CurseForge fileids available: {len(avaliable_fileids)}")
    avaliable_fingerprints = check_curseforge_fingerprints_available()
    modids.extend(avaliable_fingerprints)
    log.info(f"CurseForge fingerprints available: {len(avaliable_fingerprints)}")

    modids = [modid for modid in modids if modid >= 30000]  # 排除掉 0-30000 的 modid
    return modids


def sync_curseforge_queue() -> bool:
    log.info("Start fetching curseforge queue.")

    modids = fetch_curseforge_fileids_from_queue()
    new_modids = check_new_modids(modids=modids)
    log.info(f"New modids: {new_modids}, count: {len(new_modids)}")

    if modids:
        curseforge_pause_event.set()
        # pool, futures = create_tasks_pool(sync_mod, modids, MAX_WORKERS, "curseforge")
        pool, futures = create_tasks_pool(
            sync_mod, new_modids, MAX_WORKERS, "curseforge"
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
            notice = SyncNotification(
                platform="curseforge",
                projects_detail_info=projects_detail_info,
                total_catached_count=len(modids),
            )

            notice.send_to_telegram()

            log.info("All Message sent to telegram.")

    return True


def refresh_curseforge_categories() -> bool:
    log.info("Start fetching curseforge categories.")
    result = sync_categories(gameId=432)
    log.info(f"CurseForge categories sync finished, total categories: {len(result)}")
    return True


# def sync_curseforge_full():
#     log.info("Start fetching all data.")
#     total_data = {
#         "curseforge": 0,
#     }

#     if SYNC_CURSEFORGE:
#         curseforge_data = fetch_all_curseforge_data()
#         log.info(f"Curseforge data totally fetched: {len(curseforge_data)}")
#         total_data["curseforge"] = len(curseforge_data)

#     # 允许请求
#     curseforge_pause_event.set()

#     curseforge_pool, curseforge_futures = create_tasks_pool(
#         sync_mod_all_files, curseforge_data, MAX_WORKERS, "curseforge"
#     )

#     log.info(
#         f"All {len(curseforge_futures)} tasks submitted, waiting for completion..."
#     )

#     for future in as_completed(curseforge_futures):
#         # 不需要返回值
#         pass

#     curseforge_pool.shutdown()
