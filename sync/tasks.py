import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from database.mongodb import init_mongodb_syncengine, sync_mongo_engine
from models.database.modrinth import Version
from utils.loger import log
from utils.telegram import Notification
from utils import SyncMode
from config import Config
from models.database.curseforge import Mod
from models.database.modrinth import Project
from sync.curseforge import sync_mod, sync_mod_all_files
from sync.modrinth import sync_project, sync_project_all_version
from sync.check import (
    fetch_all_curseforge_data,
    fetch_all_modrinth_data,
    fetch_expired_curseforge_data,
    fetch_expired_modrinth_data,
    fetch_modrinth_data_by_sync_at,
    check_curseforge_fileids_available,
    check_curseforge_modids_available,
    check_curseforge_fingerprints_available,
    check_modrinth_project_ids_available,
    check_modrinth_version_ids_available,
    check_modrinth_hashes_available,
)
from sync.queue import (
    clear_curseforge_all_queues,
    clear_modrinth_all_queues,
)
from exceptions import ResponseCodeException, TooManyRequestsException


config = Config.load()

# 429 全局暂停
curseforge_pause_event = threading.Event()
modrinth_pause_event = threading.Event()

SYNC_CURSEFORGE: bool = config.sync_curseforge
SYNC_MODRINTH: bool = config.sync_modrinth
MAX_WORKERS: int = config.max_workers


def sync_with_pause(sync_function, *args):
    times = 0
    if "curseforge" in threading.current_thread().name:
        pause_event = curseforge_pause_event
        thread_type = "CurseForge"
    elif "modrinth" in threading.current_thread().name:
        pause_event = modrinth_pause_event
        thread_type = "Modrinth"
    else:
        log.error(
            f"Unknown thread name {threading.current_thread().name}, can't determine pause event."
        )
        return
    while times < 3:
        # 检查是否需要暂停
        pause_event.wait()
        try:
            sync_function(*args)
        except (ResponseCodeException, TooManyRequestsException) as e:
            if e.status_code in [429, 403]:
                log.warning(
                    f"Received HTTP {e.status_code}, pausing all {thread_type} threads for 30 seconds..."
                )
                pause_event.clear()
                time.sleep(30)
                pause_event.set()
                log.info("Resuming all threads.")
        else:
            break
    else:
        log.error(
            f"Failed to sync data after 3 retries, func: {sync_function}, args: {args}"
        )


def create_tasks_pool(sync_function, data, max_workers, thread_name_prefix):
    thread_pool = ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix=thread_name_prefix
    )
    futures = [
        thread_pool.submit(sync_with_pause, sync_function, item) for item in data
    ]
    return thread_pool, futures


async def refresh_with_modify_date():
    log.info("Start fetching expired data.")
    notification = Notification()

    # fetch all expired data
    curseforge_expired_data = []
    modrinth_expired_data = []
    if SYNC_CURSEFORGE:
        curseforge_expired_data = fetch_expired_curseforge_data()
        notification.curseforge_refreshed_count = len(curseforge_expired_data)
        log.info(
            f"Curseforge expired data totally fetched: {notification.curseforge_refreshed_count}"
        )
    if SYNC_MODRINTH:
        modrinth_expired_data = fetch_expired_modrinth_data()
        notification.modrinth_refreshed_count = len(modrinth_expired_data)
        log.info(
            f"Modrinth expired data totally fetched: {notification.modrinth_refreshed_count}"
        )

    notification.sync_mode = SyncMode.MODIFY_DATE
    log.info(
        f"All expired data fetched \
            curseforge: {notification.curseforge_refreshed_count}, \
            modrinth: {notification.modrinth_refreshed_count}, \
            start syncing..."
    )

    # 允许请求
    curseforge_pause_event.set()
    modrinth_pause_event.set()

    curseforge_pool, curseforge_futures = create_tasks_pool(
        sync_mod_all_files, curseforge_expired_data, MAX_WORKERS, "curseforge"
    )
    modrinth_pool, modrinth_futures = create_tasks_pool(
        sync_project_all_version, modrinth_expired_data, MAX_WORKERS, "modrinth"
    )

    log.info(
        f"All {len(curseforge_futures) + len(modrinth_futures)} tasks submitted, waiting for completion..."
    )

    for future in as_completed(curseforge_futures + modrinth_futures):
        # 不需要返回值
        pass
    else:
        curseforge_pool.shutdown()
        modrinth_pool.shutdown()

    # log.info(
    #     f"All expired data sync finished, total: {total_expired_count}. Next run at: {sync_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    # )

    await notification.notify_result_to_telegram()

    log.info("All Message sent to telegram.")


async def sync_modrinth_full():
    log.info("Start fetching all data.")
    total_data = {
        "modrinth": 0,
    }

    if SYNC_MODRINTH:
        modrinth_data = fetch_all_modrinth_data()
        log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
        total_data["modrinth"] = len(modrinth_data)

    # 允许请求
    modrinth_pause_event.set()

    modrinth_pool, modrinth_futures = create_tasks_pool(
        sync_project_all_version, modrinth_data, MAX_WORKERS, "modrinth"
    )

    log.info(f"All {len(modrinth_futures)} tasks submitted, waiting for completion...")

    for future in as_completed(modrinth_futures):
        # 不需要返回值
        pass

    modrinth_pool.shutdown()

    # log.info(
    #     f"All data sync finished, total: {total_data}. Next run at: {sync_full_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    # )


async def sync_curseforge_full():
    log.info("Start fetching all data.")
    total_data = {
        "curseforge": 0,
    }

    if SYNC_CURSEFORGE:
        curseforge_data = fetch_all_curseforge_data()
        log.info(f"Curseforge data totally fetched: {len(curseforge_data)}")
        total_data["curseforge"] = len(curseforge_data)

    # 允许请求
    curseforge_pause_event.set()

    curseforge_pool, curseforge_futures = create_tasks_pool(
        sync_mod_all_files, curseforge_data, MAX_WORKERS, "curseforge"
    )

    log.info(
        f"All {len(curseforge_futures)} tasks submitted, waiting for completion..."
    )

    for future in as_completed(curseforge_futures):
        # 不需要返回值
        pass

    curseforge_pool.shutdown()

    # log.info(
    #     f"All data sync finished, total: {total_data}. Next run at: {sync_full_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    # )


async def sync_modrinth_by_sync_at():
    log.info("Start fetching all data.")
    total_data = {
        "modrinth": 0,
    }

    if SYNC_MODRINTH:
        modrinth_data = fetch_modrinth_data_by_sync_at()
        log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
        total_data["modrinth"] = len(modrinth_data)

    # 允许请求
    modrinth_pause_event.set()

    modrinth_pool, modrinth_futures = create_tasks_pool(
        sync_project_all_version, modrinth_data, MAX_WORKERS, "modrinth"
    )

    log.info(f"All {len(modrinth_futures)} tasks submitted, waiting for completion...")

    for future in as_completed(modrinth_futures):
        # 不需要返回值
        pass

    modrinth_pool.shutdown()

    # log.info(
    #     f"All data sync finished, total: {total_data}. Next run at: {sync_full_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    # )


# async def sync_full():
#     sync_job.pause()
#     log.info("Start full sync, stop dateime_based sync.")
#     try:
#         log.info("Start fetching all data.")
#         total_data = {
#             "curseforge": 0,
#             "modrinth": 0,
#         }
#         # fetch all data
#         if SYNC_CURSEFORGE:
#             curseforge_data = fetch_all_curseforge_data()
#             log.info(f"Curseforge data totally fetched: {len(curseforge_data)}")
#             total_data["curseforge"] = len(curseforge_data)
#         if SYNC_MODRINTH:
#             modrinth_data = fetch_all_modrinth_data()
#             log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
#             total_data["modrinth"] = len(modrinth_data)

#         # 允许请求
#         curseforge_pause_event.set()
#         modrinth_pause_event.set()

#         # start two threadspool to sync curseforge and modrinth
#         with ThreadPoolExecutor(
#             max_workers=MAX_WORKERS, thread_name_prefix="curseforge"
#         ) as curseforge_executor, ThreadPoolExecutor(
#             max_workers=MAX_WORKERS, thread_name_prefix="modrinth"
#         ) as modrinth_executor:
#             curseforge_futures = [
#                 curseforge_executor.submit(sync_with_pause, sync_mod_all_files, modid)
#                 for modid in curseforge_data
#             ]
#             modrinth_futures = [
#                 modrinth_executor.submit(
#                     sync_with_pause, sync_project_all_version, project_id
#                 )
#                 for project_id in modrinth_data
#             ]

#             log.info(
#                 f"All {len(curseforge_futures) + len(modrinth_futures)} tasks submitted, waiting for completion..."
#             )

#             for future in as_completed(curseforge_futures + modrinth_futures):
#                 # 不需要返回值
#                 pass

#         log.info(
#             f"All data sync finished, total: {total_data}. Next run at: {sync_full_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
#         )

#         await notify_result_to_telegram(total_data, sync_mode=SyncMode.FULL)
#         log.info("All Message sent to telegram.")
#     except Exception as e:
#         log.error(f"Full sync failed: {e}")
#     finally:
#         sync_job.resume()
#         log.info("Full sync finished, resume dateime_based sync.")


def sync_curseforge_queue():
    log.info("Start fetching curseforge queue.")
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

    modids = list(set(modids))
    log.info(f"Total modids: {len(modids)} to sync.")

    if modids:
        curseforge_pause_event.set()
        pool, futures = create_tasks_pool(sync_mod, modids, MAX_WORKERS, "curseforge")

        for future in as_completed(futures):
            # 不需要返回值
            pass

        pool.shutdown()
        log.info(f"CurseForge queue sync finished, total: {len(modids)}")

        # clear queue
        clear_curseforge_all_queues()
        log.info("CurseForge queue cleared.")


def sync_modrinth_queue():
    log.info("Start fetching modrinth queue.")
    project_ids = []

    avaliable_project_ids = check_modrinth_project_ids_available()
    project_ids.extend(avaliable_project_ids)
    log.info(f"Modrinth project ids available: {len(avaliable_project_ids)}")
    avaliable_version_ids = check_modrinth_version_ids_available()
    project_ids.extend(avaliable_version_ids)
    log.info(f"Modrinth version ids available: {len(avaliable_version_ids)}")
    avaliable_hashes = check_modrinth_hashes_available()
    project_ids.extend(avaliable_hashes)
    log.info(f"Modrinth hashes available: {len(avaliable_hashes)}")

    project_ids = list(set(project_ids))
    log.info(f"Total project ids: {len(project_ids)} to sync.")

    if project_ids:
        modrinth_pause_event.set()
        pool, futures = create_tasks_pool(
            sync_project, project_ids[:2], MAX_WORKERS, "modrinth"
        )

        for future in as_completed(futures):
            # 不需要返回值
            pass

        pool.shutdown()
        log.info(f"Modrinth queue sync finished, total: {len(project_ids)}")

        # clear queue
        clear_modrinth_all_queues()
        log.info("Modrinth queue cleared.")