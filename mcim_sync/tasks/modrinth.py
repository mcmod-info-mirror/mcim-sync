from concurrent.futures import as_completed

from mcim_sync.utils.loger import log
from mcim_sync.utils.constans import Platform
from mcim_sync.utils.telegram import (
    QueueSyncNotification,
    SearchSyncNotification,
    RefreshNotification,
    TagsNotification,
)
from mcim_sync.config import Config
from mcim_sync.sync.modrinth import (
    sync_project,
    sync_categories,
    sync_loaders,
    sync_game_versions,
)
from mcim_sync.checker.modrinth import (
    check_new_project_ids,
    check_modrinth_project_ids_available,
    check_modrinth_version_ids_available,
    check_modrinth_hashes_available,
    check_newest_search_result,
)
from mcim_sync.cleaner.modrinth import remove_projects
from mcim_sync.fetcher.modrinth import fetch_expired_and_removed_modrinth_data, fetch_all_modrinth_data
from mcim_sync.queues.modrinth import clear_modrinth_all_queues
from mcim_sync.tasks import create_tasks_pool

config = Config.load()

MAX_WORKERS: int = config.max_workers


def refresh_modrinth_with_modify_date() -> bool:
    log.info("Start fetching expired Modrinth data.")

    modrinth_expired_data, modrinth_removed_data = (
        fetch_expired_and_removed_modrinth_data()
    )

    log.info(
        f"Modrinth expired data fetched: {len(modrinth_expired_data)}, removed data: {len(modrinth_removed_data)}"
    )

    # 删除已经源删除的 modrinth 数据
    if modrinth_removed_data:
        log.info(f"Start removing modrinth data: {len(modrinth_removed_data)}")
        remove_projects(modrinth_removed_data)
        log.info(f"Removed {len(modrinth_removed_data)} modrinth data.")
        log.debug(f"Modrinth removed data: {modrinth_removed_data}")

    # 刷新过期的 modrinth 数据
    log.info("Start syncing Modrinth expired data...")
    modrinth_pool, modrinth_futures = create_tasks_pool(
        sync_project,  # 需要 ProjectDetail 返回值
        modrinth_expired_data,
        MAX_WORKERS,
        "refresh_modrinth",
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
            platform=Platform.MODRINTH,
            projects_detail_info=projects_detail_info,
        )
        notification.send_to_telegram()
        log.info("Modrinth refresh message sent to telegram.")

    return True


def fetch_modrinth_not_found_ids_from_queue():
    """
    获取 modrinth 队列中的所有 project ids，检查是否真的存在
    """
    project_ids = []
    avaliable_project_ids = check_modrinth_project_ids_available()
    project_ids.extend(avaliable_project_ids)
    log.info(f"Modrinth project ids queue available project_ids: {len(avaliable_project_ids)}")
    avaliable_project_ids = check_modrinth_version_ids_available()
    project_ids.extend(avaliable_project_ids)
    log.info(f"Modrinth version ids queue available project_ids: {len(avaliable_project_ids)}")
    avaliable_project_ids = check_modrinth_hashes_available()
    project_ids.extend(avaliable_project_ids)
    log.info(f"Modrinth hashes queue available project_ids: {len(avaliable_project_ids)}")
    return project_ids


def sync_modrinth_queue() -> bool:
    log.info("Start fetching modrinth queue.")

    project_ids = fetch_modrinth_not_found_ids_from_queue()
    project_ids = list(set(project_ids))
    log.info(f"Total project ids: {len(project_ids)} to check.")

    # 只要新的 project ids
    new_project_ids = check_new_project_ids(project_ids=project_ids)
    log.info(f"New project ids: {new_project_ids}, count: {len(new_project_ids)}")

    if new_project_ids:
        pool, futures = create_tasks_pool(
            # sync_project, project_ids, MAX_WORKERS, "modrinth"
            sync_project,
            new_project_ids,
            MAX_WORKERS,
            "sync_modrinth_by_queue",  # https://github.com/mcmod-info-mirror/mcim-sync/issues/2
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
            notice = QueueSyncNotification(
                platform=Platform.MODRINTH,
                projects_detail_info=projects_detail_info,
                total_catached_count=len(project_ids),
            )
            notice.send_to_telegram()

            log.info("All Message sent to telegram.")

    return True


def sync_modrinth_by_search():
    """
    从搜索接口拉取 modrinth 的 new project id
    """
    log.info("Start fetching new modrinth project ids by search.")
    new_project_ids = check_newest_search_result()
    log.info(f"Modrinth project ids fetched: {len(new_project_ids)}")
    if new_project_ids:
        pool, futures = create_tasks_pool(
            sync_project,
            new_project_ids,
            MAX_WORKERS,
            "sync_modrinth_by_search",
        )

        projects_detail_info = []
        for future in as_completed(futures):
            result = future.result()
            if result:
                projects_detail_info.append(result)

        pool.shutdown()
        log.info(
            f"Modrinth sync new project by search finished, total: {len(new_project_ids)}"
        )

        if config.telegram_bot:
            notice = SearchSyncNotification(
                platform=Platform.MODRINTH,
                projects_detail_info=projects_detail_info,
                total_catached_count=len(new_project_ids),
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

    if config.telegram_bot:
        TagsNotification(
            categories_catached_count=category_count,
            loaders_cached_count=loader_count,
            game_versions_cached_count=game_version_count,
        ).send_to_telegram()
        log.info("All Message sent to telegram.")
    return True

def refresh_modrinth_full():
    """
    刷新 modrinth 所有数据
    """
    log.info("Start refreshing modrinth full data.")

    modrinth_data = fetch_all_modrinth_data()
    log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")

    modrinth_pool, modrinth_futures = create_tasks_pool(
        sync_project, modrinth_data, MAX_WORKERS, "modrinth_refresh_full"
    )

    log.info(
        f"All {len(modrinth_futures)} tasks submitted, waiting for completion..."
    )

    projects_detail_info = []
    for future in as_completed(modrinth_futures):
        result = future.result()
        if result:
            projects_detail_info.append(result)
    else:
        modrinth_pool.shutdown()

    success_project_ids = [project.id for project in projects_detail_info if project]
    
    failed_count = len(modrinth_data) - len(success_project_ids)
    failed_project_ids = [project.id for project in modrinth_data if project.id not in success_project_ids]

    log.info(
        f"Modrinth full sync finished, total: {len(modrinth_data)}, "
        f"success: {len(success_project_ids)}, failed: {failed_count}, "
        f"failed project ids: {failed_project_ids}"
    )

    if config.telegram_bot:
        notice = RefreshNotification(
            platform=Platform.MODRINTH,
            projects_detail_info=projects_detail_info,
            failed_count=failed_count,
        )
        notice.send_to_telegram()
        log.info("Modrinth full refresh message sent to telegram.")
    
    return True