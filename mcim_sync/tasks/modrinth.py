import threading
import time
from concurrent.futures import as_completed

from mcim_sync.utils.loger import log
from mcim_sync.utils.telegram import (
    SyncNotification,
    RefreshNotification,
)
from mcim_sync.config import Config
from mcim_sync.sync.modrinth import sync_project, sync_categories, sync_loaders, sync_game_versions
from mcim_sync.checker.modrinth import (
    check_new_project_ids,
    check_modrinth_project_ids_available,
    check_modrinth_version_ids_available,
    check_modrinth_hashes_available,
)
from mcim_sync.fetcher.modrinth import fetch_expired_modrinth_data
from mcim_sync.queues.modrinth import clear_modrinth_all_queues
from mcim_sync.tasks import create_tasks_pool, modrinth_pause_event

config = Config.load()

MAX_WORKERS: int = config.max_workers


def refresh_modrinth_with_modify_date() -> bool:
    log.info("Start fetching expired Modrinth data.")

    if config.sync_modrinth:
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

def refresh_modrinth_tags():
    log.info("Start fetching modrinth tags.")
    category_count = len(sync_categories())
    log.info(f"Modrinth Category count: {category_count}")
    loader_count = len(sync_loaders())
    log.info(f"Modrinth Loader count: {loader_count}")
    game_version_count = len(sync_game_versions())
    log.info(f"Modrinth Game Version count: {game_version_count}")
    log.info("Modrinth tags sync finished.")
    return True