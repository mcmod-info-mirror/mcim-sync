"""
定时刷新过期的数据

1. 从数据库中读取所有的数据，列出所有的 Mod 和 Project

2. 遍历所有的数据，判断是否过期

3. 如果过期，更新数据；如果未过期，跳过

4. 异步更新数据，限制并发数；先进行 Curseforge 再 Modrinth

Tips:

为了避免过多的请求，在检测到 Curseforge 403 时，暂停请求 5 分钟；根据 Modrinth API 的 headers，可以判断是否需要暂停
"""

from odmantic import query
from typing import Union, List, Set

from database.mongodb import init_mongodb_syncengine, sync_mongo_engine
from utils.loger import log
from config import MCIMConfig
from models.database.curseforge import Mod
from models.database.modrinth import Project
from sync.curseforge import fetch_mutil_mods_info
from sync.modrinth import fetch_mutil_projects_info

LIMIT_SIZE = 100

def fetch_all_expired_data():
    curseforge_expired_data = fetch_expired_curseforge_data()
    log.info(f"Curseforge expired data totally fetched: {len(curseforge_expired_data)}")
    modrinth_expired_data = fetch_expired_modrinth_data()
    log.info(f"Modrinth expired data totally fetched: {len(modrinth_expired_data)}")

    return curseforge_expired_data, modrinth_expired_data

def check_curseforge_data_updated(mods: List[Mod]) -> Set[int]:
    mod_date = {mod.id: mod.dateModified for mod in mods}
    info = fetch_mutil_projects_info()["data"]
    for mod in info:
        if mod_date.get(mod["id"]) is not None:
            if mod_date[mod["id"]] == mod["dateModified"]:
                log.info(f"Mod {mod.id} is not updated, pass!")
                del mod_date[mod["id"]]
    return set(mod_date.keys())

def check_modrinth_data_updated(projects: List[Project]) -> Set[str]:
    project_date = {project.id: project.updated for project in projects}
    info = fetch_mutil_projects_info()["data"]
    for project in info:
        if project_date.get(project["id"]) is not None:
            if project_date[project["id"]] == project["dateModified"]:
                log.info(f"Project {project['id']} is not updated, pass!")
                del project_date[project["id"]]
    return set(project_date.keys())

def fetch_expired_curseforge_data() -> List[int]:
    # Mod collection
    # 分页拉取
    expired_modids = set()
    while True:
        skip = 0
        mods_result: List[Mod] = sync_mongo_engine.find(Mod, Mod.found == True, skip=skip, limit=LIMIT_SIZE)
        if not mods_result:
            break
        skip += LIMIT_SIZE
        check_expired_result = check_curseforge_data_updated(mods_result)
        expired_modids.update(check_expired_result)
        log.info(f'Matched {len(check_expired_result)} expired mods')
    return list(expired_modids)

def fetch_expired_modrinth_data() -> List[str]:
    # Project collection
    # 分页拉取
    expired_project_ids = set()
    while True:
        skip = 0
        projects_result: List[Project] = sync_mongo_engine.find(Project, Project.found == True, skip=skip, limit=LIMIT_SIZE)
        if not projects_result:
            break
        skip += LIMIT_SIZE
        check_expired_result = check_curseforge_data_updated(projects_result)
        expired_project_ids.update(check_expired_result)
        log.info(f'Matched {len(check_expired_result)} expired projects')

    return list(expired_project_ids)

def sync_curseforge_mod(modid: int):
    pass

def sync_modrinth_project(project_id: str):
    pass

def sync_curseforge_mods(modids: List[int]):
    pass

def sync_modrinth_projects(project_ids: List[str]):
    pass
        

if __name__ == "__main__":
    init_mongodb_syncengine()
    log.info("MongoDB SyncEngine initialized.")
    mcim_config = MCIMConfig.load()
    log.info(f"MCIMConfig loaded: {mcim_config}")

    # fetch all expired data
    curseforge_expired_data, modrinth_expired_data = fetch_all_expired_data()
    
    # sync all expired data in chunks
    # start two threadspool to sync curseforge and modrinth data
    # limit the concurrency