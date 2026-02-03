from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import time

from mcim_sync.database.mongodb import init_mongodb_syncengine
from mcim_sync.database._redis import init_redis_syncengine
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.tasks.modrinth import (
    sync_modrinth_queue,
    refresh_modrinth_full,
    refresh_modrinth_with_modify_date,
    refresh_modrinth_tags,
    sync_modrinth_by_search,
    
)
from mcim_sync.tasks.curseforge import (
    sync_curseforge_queue,
    refresh_curseforge_with_modify_date,
    refresh_curseforge_categories,
    sync_curseforge_by_search,
    sync_curseforge_full
)
from mcim_sync.tasks.misc import send_statistics_to_telegram
from mcim_sync.utils.constants import GAME_432_CLASSES_INFO, GAME_78022_CLASSES_INFO

config = Config.load()
log.info("MCIMConfig loaded.")


def main():
    init_mongodb_syncengine()
    init_redis_syncengine()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = BackgroundScheduler()
    if config.job_config.curseforge_refresh:
        curseforge_refresh_trigger = CronTrigger.from_crontab(config.cron_trigger.curseforge_refresh) if config.use_cron else IntervalTrigger(seconds=config.interval.curseforge_refresh)
        scheduler.add_job(
            refresh_curseforge_with_modify_date,
            trigger=curseforge_refresh_trigger,
            name="curseforge_refresh",
        )
        log.info(f"Next run time of curseforge_refresh: {curseforge_refresh_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.modrinth_refresh:
        modrinth_refresh_trigger = CronTrigger.from_crontab(config.cron_trigger.modrinth_refresh) if config.use_cron else IntervalTrigger(seconds=config.interval.modrinth_refresh)
        scheduler.add_job(
            refresh_modrinth_with_modify_date,
            trigger=modrinth_refresh_trigger,
            name="modrinth_refresh",
        )
        log.info(f"Next run time of modrinth_refresh: {modrinth_refresh_trigger.get_next_fire_time(None, datetime.now())}")
    
    if config.job_config.curseforge_refresh_full:
        curseforge_full_refresh_trigger = CronTrigger.from_crontab(config.cron_trigger.curseforge_refresh_full) if config.use_cron else IntervalTrigger(seconds=config.interval.curseforge_refresh_full)
        scheduler.add_job(
            sync_curseforge_full,
            trigger=curseforge_full_refresh_trigger,
            name="curseforge_full_refresh",
        )
        log.info(f"Next run time of curseforge_full_refresh: {curseforge_full_refresh_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.modrinth_refresh_full:
        modrinth_full_refresh_trigger = CronTrigger.from_crontab(config.cron_trigger.modrinth_refresh_full) if config.use_cron else IntervalTrigger(seconds=config.interval.modrinth_refresh_full)
        scheduler.add_job(
            refresh_modrinth_full,
            trigger=modrinth_full_refresh_trigger,
            name="modrinth_full_refresh",
        )
        log.info(f"Next run time of modrinth_full_refresh: {modrinth_full_refresh_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.sync_curseforge_by_queue:
        curseforge_sync_trigger = CronTrigger.from_crontab(config.cron_trigger.sync_curseforge_by_queue) if config.use_cron else IntervalTrigger(seconds=config.interval.sync_curseforge_by_queue)
        scheduler.add_job(
            sync_curseforge_queue,
            trigger=curseforge_sync_trigger,
            name="sync_curseforge_queue",
        )
        log.info(f"Next run time of sync_curseforge_queue: {curseforge_sync_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.sync_modrinth_by_queue:
        modrinth_sync_trigger = CronTrigger.from_crontab(config.cron_trigger.sync_modrinth_by_queue) if config.use_cron else IntervalTrigger(seconds=config.interval.sync_modrinth_by_queue)
        scheduler.add_job(
            sync_modrinth_queue,
            trigger=modrinth_sync_trigger,
            name="sync_modrinth_queue",
        )
        log.info(f"Next run time of sync_modrinth_by_queue: {modrinth_sync_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.sync_modrinth_by_search:
        sync_modrinth_by_search_trigger = CronTrigger.from_crontab(config.cron_trigger.sync_modrinth_by_search) if config.use_cron else IntervalTrigger(seconds=config.interval.sync_modrinth_by_search)
        scheduler.add_job(
            sync_modrinth_by_search,
            trigger=sync_modrinth_by_search_trigger,
            name="sync_modrinth_by_search",
        )
        log.info(f"Next run time of sync_modrinth_by_search: {sync_modrinth_by_search_trigger.get_next_fire_time(None, datetime.now())}")

    if config.job_config.sync_curseforge_by_search:
        sync_curseforge_by_search_trigger_432 = CronTrigger.from_crontab(config.cron_trigger.sync_curseforge_by_search) if config.use_cron else IntervalTrigger(seconds=config.interval.sync_curseforge_by_search)
        scheduler.add_job(
            sync_curseforge_by_search,
            kwargs={"gameId": 432, "classes_info": GAME_432_CLASSES_INFO},
            trigger=sync_curseforge_by_search_trigger_432,
            name="sync_curseforge_by_search_432",
        )
        log.info(f"Next run time of sync_curseforge_by_search_432: {sync_curseforge_by_search_trigger_432.get_next_fire_time(None, datetime.now())}")

        sync_curseforge_by_search_trigger_78022 = CronTrigger.from_crontab(config.cron_trigger.sync_curseforge_by_search) if config.use_cron else IntervalTrigger(seconds=config.interval.sync_curseforge_by_search)
        scheduler.add_job(
            sync_curseforge_by_search,
            kwargs={"gameId": 78022, "classes_info": GAME_78022_CLASSES_INFO},
            trigger=sync_curseforge_by_search_trigger_78022,
            name="sync_curseforge_by_search_78022",
        )
        log.info(f"Next run time of sync_curseforge_by_search_78022: {sync_curseforge_by_search_trigger_78022.get_next_fire_time(None, datetime.now())}")

    if config.job_config.curseforge_categories:
        curseforge_categories_trigger_432 = CronTrigger.from_crontab(config.cron_trigger.curseforge_categories) if config.use_cron else IntervalTrigger(seconds=config.interval.curseforge_categories)
        scheduler.add_job(
            refresh_curseforge_categories,
            kwargs={"gameId": 432},
            trigger=curseforge_categories_trigger_432,
            name="curseforge_categories_refresh_432",
        )
        log.info(f"Next run time of curseforge_categories_refresh_432: {curseforge_categories_trigger_432.get_next_fire_time(None, datetime.now())}")

        curseforge_categories_trigger_78022 = CronTrigger.from_crontab(config.cron_trigger.curseforge_categories) if config.use_cron else IntervalTrigger(seconds=config.interval.curseforge_categories)
        scheduler.add_job(
            refresh_curseforge_categories,
            kwargs={"gameId": 78022},
            trigger=curseforge_categories_trigger_78022,
            name="curseforge_categories_refresh_78022",
        )
        log.info(f"Next run time of curseforge_categories_refresh_78022: {curseforge_categories_trigger_78022.get_next_fire_time(None, datetime.now())}")

    if config.job_config.modrinth_tags:
        modrinth_tags_trigger = CronTrigger.from_crontab(config.cron_trigger.modrinth_tags) if config.use_cron else IntervalTrigger(seconds=config.interval.modrinth_tags)
        scheduler.add_job(
            refresh_modrinth_tags,
            trigger=modrinth_tags_trigger,
            name="modrinth_refresh_tags",
        )
        log.info(f"Next run time of modrinth_refresh_tags: {modrinth_tags_trigger.get_next_fire_time(None, datetime.now())}")

    if config.telegram_bot and config.job_config.global_statistics:
        statistics_trigger = CronTrigger.from_crontab(config.cron_trigger.global_statistics) if config.use_cron else IntervalTrigger(seconds=config.interval.global_statistics)
        scheduler.add_job(
            send_statistics_to_telegram,
            trigger=statistics_trigger,
            name="statistics",
        )
        log.info(f"Next run time of global_statistics: {statistics_trigger.get_next_fire_time(None, datetime.now())}")

    # 启动调度器
    scheduler.start()
    log.info("Scheduler started")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler shutdown")


if __name__ == "__main__":
    main()