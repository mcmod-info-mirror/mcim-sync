# Desc: 启动文件，用于启动定时任务，定时同步 CurseForge 和 Modrinth 的数据
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Union, List, Set
import datetime
import threading
import time

from database.mongodb import init_mongodb_syncengine, sync_mongo_engine
from utils.loger import log
from config import MCIMConfig
from models.database.curseforge import Mod
from models.database.modrinth import Project
from sync.curseforge import fetch_mutil_mods_info, sync_mod_all_files
from sync.modrinth import fetch_mutil_projects_info, sync_project_all_version
from exceptions import ResponseCodeException

mcim_config = MCIMConfig.load()
log.info(f"MCIMConfig loaded.")

CURSEFORGE_LIMIT_SIZE: int = mcim_config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = mcim_config.modrinth_chunk_size
SYNC_CURSEFORGE: bool = mcim_config.sync_curseforge
SYNC_MODRINTH: bool = mcim_config.sync_modrinth
MAX_WORKERS: int = mcim_config.max_workers

# 429 全局暂停
pause_event = threading.Event()


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
    project_date = {project.id: {"sync_date": project.updated} for project in projects}
    info = fetch_mutil_projects_info(project_ids=[project.id for project in projects])
    expired_project_ids: Set[str] = set()
    models: List[Project] = []
    for project in info:
        models.append(Project(**project))
        project_id = project["id"]
        sync_date = project_date[project_id]["sync_date"]
        project_date[project_id]["source_date"] = project["updated"]
        if sync_date == project["updated"]:
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


def sync_with_pause(sync_function, *args):
    times = 0
    while times < 3:
        # 检查是否需要暂停
        pause_event.wait()
        try:
            sync_function(*args)
        except ResponseCodeException as e:
            if e.status_code in [429, 403]:
                log.warning(
                    f"Received HTTP {e.status_code}, pausing all curseforge threads for 30 seconds..."
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


def sync_one_time():
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
    pause_event.set()

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


if __name__ == "__main__":
    init_mongodb_syncengine()
    log.info("MongoDB SyncEngine initialized.")

    # 创建调度器
    scheduler = BackgroundScheduler()

    # 添加定时任务，每小时执行一次
    sync_job = scheduler.add_job(
        sync_one_time,
        IntervalTrigger(seconds=mcim_config.interval),
        next_run_time=datetime.datetime.now(),  # 立即执行一次任务
        name="mcim_sync",
    )

    # 启动调度器
    scheduler.start()
    log.info("Scheduler started.")

    # 主循环，保持程序运行
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler shutdown.")
