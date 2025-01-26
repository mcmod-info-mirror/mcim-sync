import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.loger import log
from utils.telegram import (
    SyncNotification,
    RefreshNotification,
    StatisticsNotification,
)
from config import Config
from sync.curseforge import sync_mod, sync_categories
from sync.modrinth import sync_project
from sync.check import (
    # fetch_all_curseforge_data,
    # fetch_all_modrinth_data,
    fetch_expired_curseforge_data,
    fetch_expired_modrinth_data,
    # fetch_modrinth_data_by_sync_at,
    check_curseforge_fileids_available,
    check_curseforge_modids_available,
    check_curseforge_fingerprints_available,
    check_modrinth_project_ids_available,
    check_modrinth_version_ids_available,
    check_modrinth_hashes_available,
    check_new_modids,
    check_new_project_ids,
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
            return sync_function(*args)

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


def refresh_curseforge_with_modify_date() -> bool:
    log.info("Start fetching expired CurseForge data.")

    if SYNC_CURSEFORGE:
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


def refresh_modrinth_with_modify_date() -> bool:
    log.info("Start fetching expired Modrinth data.")

    if SYNC_MODRINTH:
        modrinth_expired_data = fetch_expired_modrinth_data()

        log.info(f"Modrinth expired data fetched: {len(modrinth_expired_data)}")
        log.info(f"Start syncing Modrinth expired data...")

        modrinth_pause_event.set()
        modrinth_pool, modrinth_futures = create_tasks_pool(
            sync_project,  # 需要 ProjectDetail 返回值
            modrinth_expired_data,
            MAX_WORKERS,
            "modrinth",
        )

        projects_detail_info = []
        for future in as_completed(modrinth_futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)
        else:
            modrinth_pool.shutdown()

        if config.telegram_bot:
            notification = RefreshNotification(
                platform="Modrinth",
                projects_detail_info=projects_detail_info,
            )
            notification.send_to_telegram()
            log.info("Modrinth refresh message sent to telegram.")

    return True


# def sync_modrinth_full():
#     log.info("Start fetching all data.")
#     total_data = {
#         "modrinth": 0,
#     }

#     if SYNC_MODRINTH:
#         modrinth_data = fetch_all_modrinth_data()
#         log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
#         total_data["modrinth"] = len(modrinth_data)

#     # 允许请求
#     modrinth_pause_event.set()

#     modrinth_pool, modrinth_futures = create_tasks_pool(
#         sync_project_all_version, modrinth_data, MAX_WORKERS, "modrinth"
#     )

#     log.info(f"All {len(modrinth_futures)} tasks submitted, waiting for completion...")

#     for future in as_completed(modrinth_futures):
#         # 不需要返回值
#         pass

#     modrinth_pool.shutdown()


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


# def sync_modrinth_by_sync_at():
#     log.info("Start fetching all data.")
#     total_data = {
#         "modrinth": 0,
#     }

#     if SYNC_MODRINTH:
#         modrinth_data = fetch_modrinth_data_by_sync_at()
#         log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
#         total_data["modrinth"] = len(modrinth_data)

#     # 允许请求
#     modrinth_pause_event.set()

#     modrinth_pool, modrinth_futures = create_tasks_pool(
#         sync_project_all_version, modrinth_data, MAX_WORKERS, "modrinth"
#     )

#     log.info(f"All {len(modrinth_futures)} tasks submitted, waiting for completion...")

#     for future in as_completed(modrinth_futures):
#         # 不需要返回值
#         pass

#     modrinth_pool.shutdown()


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


def fetch_modrinth_project_ids_from_queue():
    """
    获取 modrinth 队列中的所有 project ids，检查是否真的存在
    """
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
    return project_ids


def sync_modrinth_queue() -> bool:
    log.info("Start fetching modrinth queue.")

    project_ids = fetch_modrinth_project_ids_from_queue()
    project_ids = list(set(project_ids))
    log.info(f"Total project ids: {len(project_ids)} to check.")

    # 只要新的 project ids
    new_project_ids = check_new_project_ids(project_ids=project_ids)
    log.info(f"New project ids: {new_project_ids}, count: {len(new_project_ids)}")

    if project_ids:
        modrinth_pause_event.set()
        pool, futures = create_tasks_pool(
            # sync_project, project_ids, MAX_WORKERS, "modrinth"
            sync_project,
            new_project_ids,
            MAX_WORKERS,
            "modrinth",  # https://github.com/mcmod-info-mirror/mcim-sync/issues/2
        )

        projects_detail_info = []

        for future in as_completed(futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

        pool.shutdown()
        log.info(f"Modrinth queue sync finished, total: {len(project_ids)}")

        # clear queue
        clear_modrinth_all_queues()
        log.info("Modrinth queue cleared.")

        if config.telegram_bot:
            notice = SyncNotification(
                platform="modrinth",
                projects_detail_info=projects_detail_info,
                total_catached_count=len(project_ids),
            )
            notice.send_to_telegram()

            log.info("All Message sent to telegram.")

    return True


def refresh_curseforge_categories() -> bool:
    log.info("Start fetching curseforge categories.")
    result = sync_categories()
    log.info(f"CurseForge categories sync finished, total categories: {len(result)}")
    return True

def send_statistics_to_telegram() -> bool:
    log.info("Start fetching statistics to telegram.")
    message = StatisticsNotification.send_to_telegram()
    log.info("Statistics message sent to telegram.")
    # log.info(f"Statistics message: {message}")
    return True