from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import datetime

from database.mongodb import init_mongodb_syncengine
from database._redis import init_redis_syncengine
from utils.loger import log
from config import Config
from sync.tasks import (
    refresh_with_modify_date,
    sync_curseforge_queue,
    sync_modrinth_queue,
)

config = Config.load()
log.info(f"MCIMConfig loaded.")

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size


def main():
    init_mongodb_syncengine()
    init_redis_syncengine()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = BackgroundScheduler()

    # 添加定时刷新任务，每小时执行一次
    refresh_job = scheduler.add_job(
        refresh_with_modify_date,
        trigger=IntervalTrigger(seconds=config.interval_refresh),
        next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        name="mcim_refresh",
    )

    # 添加定时同步任务，用于检查 api 未找到的请求数据
    curseforge_sync_job = scheduler.add_job(
        sync_curseforge_queue,
        trigger=IntervalTrigger(seconds=config.interval_sync_curseforge),
        name="mcim_sync_curseforge",
    )

    modrinth_sync_job = scheduler.add_job(
        sync_modrinth_queue,
        trigger=IntervalTrigger(seconds=config.interval_sync_modrinth),
        name="mcim_sync_modrinth",
    )

    # 启动调度器
    scheduler.start()
    log.info(f"Scheduler started")

    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info(f"Scheduler shutdown")

if __name__ == "__main__":
    main()