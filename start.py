from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import datetime
import time

from mcim_sync.database.mongodb import init_mongodb_syncengine
from mcim_sync.database._redis import init_redis_syncengine
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.tasks.modrinth import (
    sync_modrinth_queue,
    refresh_modrinth_with_modify_date,
    refresh_modrinth_tags,
    sync_modrinth_by_search,
)
from mcim_sync.tasks.curseforge import (
    sync_curseforge_queue,
    refresh_curseforge_with_modify_date,
    refresh_curseforge_categories,
    sync_curseforge_by_search,
)
from mcim_sync.tasks.misc import send_statistics_to_telegram

config = Config.load()
log.info("MCIMConfig loaded.")


def main():
    init_mongodb_syncengine()
    init_redis_syncengine()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = BackgroundScheduler()
    if config.job_config.curseforge_refresh:
        # 添加定时刷新任务，每小时执行一次
        curseforge_refresh_job = scheduler.add_job(
            refresh_curseforge_with_modify_date,
            trigger=IntervalTrigger(seconds=config.interval.curseforge_refresh),
            name="curseforge_refresh",
        )

    if config.job_config.modrinth_refresh:
        modrinth_refresh_job = scheduler.add_job(
            refresh_modrinth_with_modify_date,
            trigger=IntervalTrigger(seconds=config.interval.modrinth_refresh),
            name="modrinth_refresh",
        )

    if config.job_config.sync_curseforge_by_queue:
        # 添加定时同步任务，用于检查 api 未找到的请求数据
        curseforge_sync_job = scheduler.add_job(
            sync_curseforge_queue,
            trigger=IntervalTrigger(seconds=config.interval.sync_curseforge_by_queue),
            name="sync_curseforge_queue",
        )

    if config.job_config.sync_modrinth_by_queue:
        # 由 sync_modrinth_by_search 平替
        modrinth_sync_job = scheduler.add_job(
            sync_modrinth_queue,
            trigger=IntervalTrigger(seconds=config.interval.sync_modrinth_by_queue),
            name="sync_modrinth_queue",
        )

    if config.job_config.sync_curseforge_by_search:
        sync_modrinth_by_search_job = scheduler.add_job(
            sync_modrinth_by_search,
            trigger=IntervalTrigger(seconds=config.interval.sync_modrinth_by_search),
            name="sync_modrinth_by_search",
        )

    if config.job_config.sync_modrinth_by_search:
        sync_curseforge_by_search_job = scheduler.add_job(
            sync_curseforge_by_search,
            trigger=IntervalTrigger(seconds=config.interval.sync_curseforge_by_search),
            name="sync_curseforge_by_search",
        )

    if config.job_config.curseforge_categories:
        curseforge_categories_refresh_job = scheduler.add_job(
            refresh_curseforge_categories,
            # trigger=IntervalTrigger(seconds=config.interval.curseforge_categories),
            # 使用 CronTrigger 每天执行一次，指定 0 点
            trigger=CronTrigger(
                hour="0",
                minute="0",
                second="0",
                day_of_week="*",
                month="*",
                year="*",
            ),
            name="curseforge_categories_refresh",
            next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        )

    if config.job_config.modrinth_tags:
        modrinth_refresh_tags_job = scheduler.add_job(
            refresh_modrinth_tags,
            # trigger=IntervalTrigger(seconds=config.interval.modrinth_tags),
            # 使用 CronTrigger 每天执行一次
            trigger=CronTrigger(
                hour="0",
                minute="0",
                second="0",
                day_of_week="*",
                month="*",
                year="*",
            ),
            name="modrinth_refresh_tags",
            next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        )

    if config.telegram_bot and config.job_config.global_statistics:
        # 单独发布统计信息
        statistics_job = scheduler.add_job(
            send_statistics_to_telegram,
            # trigger=IntervalTrigger(seconds=config.interval.global_statistics),
            # 使用 CronTrigger 每天执行一次
            trigger=CronTrigger(
                hour="0",
                minute="0",
                second="0",
                day_of_week="*",
                month="*",
                year="*",
            ),
            name="statistics",
        )

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
