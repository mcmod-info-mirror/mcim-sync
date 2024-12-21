from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
import datetime

from database.mongodb import init_mongodb_syncengine
from utils.loger import log
from utils.telegram import init_bot
from config import Config
from sync.tasks import (
    sync_with_modify_date,
)

config = Config.load()
log.info(f"MCIMConfig loaded.")

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size


async def main():
    init_mongodb_syncengine()
    init_bot()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = AsyncIOScheduler()

    global sync_job
    # 添加定时任务，每小时执行一次
    sync_job = scheduler.add_job(
        sync_with_modify_date,
        trigger=IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        name="mcim_sync",
    )

    # 启动调度器
    scheduler.start()
    log.info(
        f"Scheduler started"  # , Next run at: {sync_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
