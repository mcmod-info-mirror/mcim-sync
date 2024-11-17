# Desc: 启动文件，用于启动定时任务，定时同步 CurseForge 和 Modrinth 的数据
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Union, List, Set
from enum import Enum
import telegram
import asyncio
import datetime
import threading
import time

from database.mongodb import init_mongodb_syncengine, sync_mongo_engine
from models.database.modrinth import Version
from utils.network import request_sync
from utils.loger import log
from config import Config
from models.database.curseforge import Mod
from models.database.modrinth import Project
from sync.curseforge import fetch_mutil_mods_info, sync_mod_all_files
from sync.modrinth import fetch_mutil_projects_info, sync_project_all_version
from exceptions import ResponseCodeException

config = Config.load()
log.info(f"MCIMConfig loaded.")

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size
SYNC_CURSEFORGE: bool = config.sync_curseforge
SYNC_MODRINTH: bool = config.sync_modrinth
MAX_WORKERS: int = config.max_workers

bot = telegram.Bot(
    token=config.bot_token,
    base_url=config.bot_api,
    request=telegram.request.HTTPXRequest(proxy=config.telegram_proxy),
)

# 429 全局暂停
curseforge_pause_event = threading.Event()
modrinth_pause_event = threading.Event()

class SyncMode(Enum):
    MODIFY_DATE = 1
    FULL = 2


# 应该尽量多次提交，少缓存在内存中
def submit_models(models: List[Union[Mod, Project]]):
    if len(models) != 0:
        sync_mongo_engine.save_all(models)
        log.debug(f"Submited models: {len(models)}")


def check_curseforge_data_updated(mods: List[Mod]) -> Set[int]:
    mod_date = {mod.id: {"sync_date": mod.dateModified} for mod in mods}
    expired_modids: Set[int] = set()
    info = fetch_mutil_mods_info(modIds=[mod.id for mod in mods])
    models: List[Mod] = []
    for mod in info:
        models.append(Mod(**mod))
        modid = mod["id"]
        mod_date[modid]["source_date"] = mod["dateModified"]
        sync_date = mod_date[modid]["sync_date"]
        if sync_date == mod["dateModified"]:
            log.debug(f"Mod {modid} is not updated, pass!")
        else:
            expired_modids.add(modid)
            log.debug(f"Mod {modid} is updated {sync_date} -> {mod['dateModified']}!")
        if len(models) >= 100:
            submit_models(models)
            models.clear()
    submit_models(models)
    return expired_modids


def check_modrinth_data_updated(projects: List[Project]) -> Set[str]:
    project_info = {
        project.id: {"sync_date": project.updated, "versions": project.versions}
        for project in projects
    }
    info = fetch_mutil_projects_info(project_ids=[project.id for project in projects])
    expired_project_ids: Set[str] = set()
    models: List[Project] = []
    for project in info:
        models.append(Project(**project))
        project_id = project["id"]
        sync_date = project_info[project_id]["sync_date"]
        project_info[project_id]["source_date"] = project["updated"]
        if sync_date == project["updated"]:
            if project_info[project_id]["versions"] != project["versions"]:
                log.debug(
                    f"Project {project_id} version count is not completely equal, some version were deleted, sync it!"
                )
                expired_project_ids.add(project_id)
            else:
                log.debug(f"Project {project_id} is not updated, pass!")
        else:
            expired_project_ids.add(project_id)
            log.debug(
                f"Project {project_id} is updated {sync_date} -> {project['updated']}!"
            )
        if len(models) >= 100:
            submit_models(models)
            models.clear()
    submit_models(models)
    return expired_project_ids


def fetch_expired_curseforge_data() -> List[int]:
    expired_modids = set()
    skip = 0
    while True:
        mods_result: List[Mod] = list(
            sync_mongo_engine.find(
                Mod, Mod.found == True, skip=skip, limit=CURSEFORGE_LIMIT_SIZE
            )
        )

        if not mods_result:
            break
        skip += CURSEFORGE_LIMIT_SIZE
        check_expired_result = check_curseforge_data_updated(mods_result)
        expired_modids.update(check_expired_result)
        log.debug(f"Matched {len(check_expired_result)} expired mods")
    return list(expired_modids)


def fetch_expired_modrinth_data() -> List[str]:
    expired_project_ids = set()
    skip = 0
    while True:
        projects_result: List[Project] = list(
            sync_mongo_engine.find(
                Project, Project.found == True, skip=skip, limit=MODRINTH_LIMIT_SIZE
            )
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        check_expired_result = check_modrinth_data_updated(projects_result)
        expired_project_ids.update(check_expired_result)
        log.debug(f"Matched {len(check_expired_result)} expired projects")
    return list(expired_project_ids)


async def notify_result_to_telegram(
    total_refreshed_data: dict, sync_mode: SyncMode = SyncMode.MODIFY_DATE
):
    sync_message = (
        f"本次同步为{'增量' if sync_mode == SyncMode.MODIFY_DATE else '全量'}同步\n"
        f"CurseForge: {total_refreshed_data['curseforge']} 个 Mod 的数据已更新\n"
        f"Modrinth: {total_refreshed_data['modrinth']} 个 Mod 的数据已更新"
    )
    await bot.send_message(chat_id=config.chat_id, text=sync_message)
    log.info(f"Message '{sync_message}' sent to telegram.")
    """
    https://mod.mcimirror.top/statistics
    {
        "curseforge": {
            "mod": 75613,
            "file": 1265312,
            "fingerprint": 1264259
        },
        "modrinth": {
            "project": 42832,
            "version": 415467,
            "file": 458877
        },
        "file_cdn": {
            "file": 924573
        }
    }
    格式化为消息
    截至 2024 年 11 月 03 日 01:58:08，MCIM 已缓存：
    Curseforge 模组 75613 个，文件 1265312 个，指纹 1264259 个
    Modrinth 项目 42832 个，版本 415467 个，文件 458877 个
    CDN 文件 924573 个
    """
    mcim_stats = request_sync("https://mod.mcimirror.top/statistics").json()
    mcim_message = (
        f"截至 {datetime.datetime.now().strftime('%Y 年 %m 月 %d 日 %H:%M:%S')}，MCIM API 已缓存：\n"
        f"Curseforge 模组 {mcim_stats['curseforge']['mod']} 个，文件 {mcim_stats['curseforge']['file']} 个，指纹 {mcim_stats['curseforge']['fingerprint']} 个\n"
        f"Modrinth 项目 {mcim_stats['modrinth']['project']} 个，版本 {mcim_stats['modrinth']['version']} 个，文件 {mcim_stats['modrinth']['file']} 个\n"
        f"CDN 文件 {mcim_stats['file_cdn']['file']} 个"
    )
    await bot.send_message(chat_id=config.chat_id, text=mcim_message)
    log.info(f"Message '{mcim_message}' sent to telegram.")
    """
    https://files.mcimirror.top/api/stats/center
    {
    "today": {
        "hits": 69546,
        "bytes": 112078832941
    },
    "onlines": 7,
    "sources": 1,
    "totalFiles": 922998,
    "totalSize": 1697281799794,
    "startTime": 1730551551412
    }
    格式化为消息
    当前在线节点：6 个
    当日全网总请求：67597 次
    当日全网总流量：100.89 GB
    同步源数量：1 个
    总文件数：922998 个
    总文件大小：1.54 TB
    主控在线时间：0 天 5 小时 12 分钟 14 秒
    请求时间：2024 年 11 月 03 日 01:58:05
    """
    files_stats = request_sync("https://files.mcimirror.top/api/stats/center").json()
    files_message = (
        f"OpenMCIM 数据统计：\n"
        f"当前在线节点：{files_stats['onlines']} 个\n"
        f"当日全网总请求：{files_stats['today']['hits']} 次\n"
        f"当日全网总流量：{files_stats['today']['bytes'] / 1024 / 1024 / 1024:.2f} GB\n"
        f"同步源数量：{files_stats['sources']} 个\n"
        f"总文件数：{files_stats['totalFiles']} 个\n"
        f"总文件大小：{files_stats['totalSize'] / 1024 / 1024 / 1024/ 1024:.2f} TB\n"
    )
    await bot.send_message(chat_id=config.chat_id, text=files_message)
    log.info(f"Message '{files_message}' sent to telegram.")


def sync_with_pause(sync_function, *args):
    times = 0
    if "curseforge" in threading.current_thread().name:
        pause_event = curseforge_pause_event
        thread_type = "CurseForge"
    elif "modrinth" in threading.current_thread().name:
        pause_event = modrinth_pause_event
        thread_type = "Modrinth"
    else:
        log.error("Unknown thread name, can't determine pause event.")
        return
    while times < 3:
        # 检查是否需要暂停
        pause_event.wait()
        try:
            sync_function(*args)
        except ResponseCodeException as e:
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


async def sync_with_modify_date():
    log.info("Start fetching expired data.")
    total_expired_data = {
        "curseforge": 0,
        "modrinth": 0,
    }
    # fetch all expired data
    curseforge_expired_data = []
    modrinth_expired_data = []
    if SYNC_CURSEFORGE:
        curseforge_expired_data = fetch_expired_curseforge_data()
        log.info(
            f"Curseforge expired data totally fetched: {len(curseforge_expired_data)}"
        )
        total_expired_data["curseforge"] = len(curseforge_expired_data)
    if SYNC_MODRINTH:
        modrinth_expired_data = fetch_expired_modrinth_data()
        log.info(f"Modrinth expired data totally fetched: {len(modrinth_expired_data)}")
        total_expired_data["modrinth"] = len(modrinth_expired_data)

    log.info(f"All expired data fetched {total_expired_data}, start syncing...")

    # 允许请求
    curseforge_pause_event.set()
    modrinth_pause_event.set()

    # start two threadspool to sync curseforge and modrinth
    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS, thread_name_prefix="curseforge"
    ) as curseforge_executor, ThreadPoolExecutor(
        max_workers=MAX_WORKERS, thread_name_prefix="modrinth"
    ) as modrinth_executor:
        curseforge_futures = [
            curseforge_executor.submit(sync_with_pause, sync_mod_all_files, modid)
            for modid in curseforge_expired_data
        ]
        modrinth_futures = [
            modrinth_executor.submit(
                sync_with_pause, sync_project_all_version, project_id
            )
            for project_id in modrinth_expired_data
        ]

        log.info(
            f"All {len(curseforge_futures) + len(modrinth_futures)} tasks submitted, waiting for completion..."
        )

        for future in as_completed(curseforge_futures + modrinth_futures):
            # 不需要返回值
            pass

    log.info(
        f"All expired data sync finished, total: {total_expired_data}. Next run at: {sync_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    await notify_result_to_telegram(total_expired_data, sync_mode=SyncMode.MODIFY_DATE)
    log.info("All Message sent to telegram.")


def fetch_all_curseforge_data() -> List[int]:
    skip = 0
    result = []
    while True:
        mods_result: List[Mod] = list(
            sync_mongo_engine.find(
                Mod, Mod.found == True, skip=skip, limit=CURSEFORGE_LIMIT_SIZE
            )
        )

        if not mods_result:
            break
        skip += CURSEFORGE_LIMIT_SIZE
        result.extend([mod.id for mod in mods_result])
    return result


def fetch_all_modrinth_data() -> List[str]:
    skip = 0
    result = []
    while True:
        projects_result: List[Project] = list(
            sync_mongo_engine.find(
                Project, Project.found == True, skip=skip, limit=MODRINTH_LIMIT_SIZE
            )
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        result.extend([project.id for project in projects_result])
    return result


async def sync_full():
    sync_job.pause()
    log.info("Start full sync, stop dateime_based sync.")
    try:
        log.info("Start fetching all data.")
        total_data = {
            "curseforge": 0,
            "modrinth": 0,
        }
        # fetch all data
        if SYNC_CURSEFORGE:
            curseforge_data = fetch_all_curseforge_data()
            log.info(f"Curseforge data totally fetched: {len(curseforge_data)}")
            total_data["curseforge"] = len(curseforge_data)
        if SYNC_MODRINTH:
            modrinth_data = fetch_all_modrinth_data()
            log.info(f"Modrinth data totally fetched: {len(modrinth_data)}")
            total_data["modrinth"] = len(modrinth_data)

        # 允许请求
        curseforge_pause_event.set()
        modrinth_pause_event.set()

        # start two threadspool to sync curseforge and modrinth
        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS, thread_name_prefix="curseforge"
        ) as curseforge_executor, ThreadPoolExecutor(
            max_workers=MAX_WORKERS, thread_name_prefix="modrinth"
        ) as modrinth_executor:
            curseforge_futures = [
                curseforge_executor.submit(sync_with_pause, sync_mod_all_files, modid)
                for modid in curseforge_data
            ]
            modrinth_futures = [
                modrinth_executor.submit(
                    sync_with_pause, sync_project_all_version, project_id
                )
                for project_id in modrinth_data
            ]

            log.info(
                f"All {len(curseforge_futures) + len(modrinth_futures)} tasks submitted, waiting for completion..."
            )

            for future in as_completed(curseforge_futures + modrinth_futures):
                # 不需要返回值
                pass

        log.info(
            f"All data sync finished, total: {total_data}. Next run at: {sync_full_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

        await notify_result_to_telegram(total_data, sync_mode=SyncMode.FULL)
        log.info("All Message sent to telegram.")
    except Exception as e:
        log.error(f"Full sync failed: {e}")
    finally:
        sync_job.resume()
        log.info("Full sync finished, resume dateime_based sync.")


async def main():
    init_mongodb_syncengine()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = AsyncIOScheduler()

    global sync_job, sync_full_job
    # 添加定时任务，每小时执行一次
    sync_job = scheduler.add_job(
        sync_with_modify_date,
        IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        name="mcim_sync",
    )

    sync_full_job = scheduler.add_job(
        sync_full,
        IntervalTrigger(seconds=config.interval_full),
        name="mcim_sync_full",
    )
    

    # 启动调度器
    scheduler.start()
    log.info(
        f"Scheduler started, Next run at: {sync_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
