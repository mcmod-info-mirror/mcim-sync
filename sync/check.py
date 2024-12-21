
from typing import Union, List, Set
import datetime
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
from exceptions import ResponseCodeException, TooManyRequestsException
from utils.telegram import send_message
from utils import submit_models

config = Config.load()

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size
MAX_WORKERS: int = config.max_workers
CURSEFORGE_DELAY: Union[float, int] = config.curseforge_delay
MODRINTH_DELAY: Union[float, int] = config.modrinth_delay

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


# fetch expired

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
        time.sleep(CURSEFORGE_DELAY)
        log.debug(f'Delay {CURSEFORGE_DELAY} seconds')
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
        time.sleep(MODRINTH_DELAY)
        log.debug(f'Delay {MODRINTH_DELAY} seconds')
    return list(expired_project_ids)

# fetch all

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
        time.sleep(CURSEFORGE_DELAY)
        log.debug(f'Delay {CURSEFORGE_DELAY} seconds')
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
        time.sleep(MODRINTH_DELAY)
        log.debug(f'Delay {MODRINTH_DELAY} seconds')
    return result

# fetch by sync_date

def fetch_modrinth_data_by_sync_at():
    skip = 0
    result = []
    while True:
        query = {
            "$expr": {
                "$lt": [
                    {"$dateFromString": {"dateString": "$sync_at"}},
                    datetime.datetime.now() - datetime.timedelta(days=1),
                ]
            }
        }
        projects_result: List[Project] = list(
            sync_mongo_engine.find(
                Project,
                # Project.found == True, skip=skip, limit=MODRINTH_LIMIT_SIZE
                query,
                skip=skip,
                limit=MODRINTH_LIMIT_SIZE,
            )
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        result.extend([project.id for project in projects_result])
        time.sleep(MODRINTH_DELAY)
        log.debug(f'Delay {MODRINTH_DELAY} seconds')
    return result

