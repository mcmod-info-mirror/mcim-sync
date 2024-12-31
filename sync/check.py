from typing import Union, List, Set
from odmantic import query
import datetime
import time

from database.mongodb import sync_mongo_engine, raw_mongo_client
from utils.loger import log
from config import Config
from models.database.curseforge import Mod
from models.database.modrinth import Project
from sync.curseforge import (
    fetch_mutil_mods_info,
    fetch_mutil_files,
    fetch_mutil_fingerprints,
)
from sync.modrinth import (
    fetch_mutil_projects_info,
    fetch_multi_versions_info,
    fetch_multi_hashes_info,
)
from sync.queue import (
    fetch_modrinth_project_ids_queue,
    fetch_modrinth_version_ids_queue,
    fetch_modrinth_hashes_queue,
    fetch_curseforge_modids_queue,
    fetch_curseforge_fileids_queue,
    fetch_curseforge_fingerprints_queue,
)
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
        log.debug(f"Delay {CURSEFORGE_DELAY} seconds")
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
        log.debug(f"Delay {MODRINTH_DELAY} seconds")
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
        log.debug(f"Delay {CURSEFORGE_DELAY} seconds")
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
        log.debug(f"Delay {MODRINTH_DELAY} seconds")
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
        log.debug(f"Delay {MODRINTH_DELAY} seconds")
    return result


# check modrinth_project_ids queue
def check_modrinth_project_ids_available():
    """
    返回对应的 project_ids
    """
    available_project_ids = []
    project_ids = fetch_modrinth_project_ids_queue()
    log.info(f'Fetched {len(project_ids)} modrinth project ids from queue')

    for i in range(0, len(project_ids), MODRINTH_LIMIT_SIZE):
        chunk = project_ids[i : i + MODRINTH_LIMIT_SIZE]
        info = fetch_mutil_projects_info(project_ids=chunk)
        # 统一缓存
        # # save in mongodb
        # models = [Project(**project) for project in info]
        # submit_models(models)
        available_project_ids.extend([project["id"] for project in info])
    return list(set(available_project_ids))


# check modrinth_version_ids queue
def check_modrinth_version_ids_available():
    """
    返回对应的 project_ids
    """
    available_project_ids = []
    version_ids = fetch_modrinth_version_ids_queue()
    log.info(f'Fetched {len(version_ids)} modrinth version ids from queue')

    for i in range(0, len(version_ids), MODRINTH_LIMIT_SIZE):
        chunk = version_ids[i : i + MODRINTH_LIMIT_SIZE]
        info = fetch_multi_versions_info(version_ids=chunk)
        available_project_ids.extend([version["project_id"] for version in info])
    return list(set(available_project_ids))


# check modrinth_hashes_{algorithm} queue
def check_modrinth_hashes_available():
    """
    返回对应的 project_ids
    """
    available_project_ids = []
    algorithms = ["sha1", "sha256"]
    for algorithm in algorithms:
        hashes = fetch_modrinth_hashes_queue(algorithm)
        log.info(f'Fetched {len(hashes)} modrinth hashes from queue')

        for i in range(0, len(hashes), MODRINTH_LIMIT_SIZE):
            chunk = hashes[i : i + MODRINTH_LIMIT_SIZE]
            info = fetch_multi_hashes_info(hashes=chunk, algorithm=algorithm)
            available_project_ids.extend([hash["project_id"] for hash in info.values()])
    return list(set(available_project_ids))


# check curseforge_modids queue
def check_curseforge_modids_available():
    """
    返回对应的 modids
    """
    available_modids = []
    modids = fetch_curseforge_modids_queue()
    log.info(f'Fetched {len(modids)} curseforge modids from queue')

    for i in range(0, len(modids), CURSEFORGE_LIMIT_SIZE):
        chunk = modids[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_mods_info(modIds=chunk)
        available_modids.extend([mod["id"] for mod in info])
    return list(set(available_modids))


# check curseforge_fileids queue
def check_curseforge_fileids_available():
    """
    返回对应的 modids
    """
    available_modids = []
    fileids = fetch_curseforge_fileids_queue()
    log.info(f'Fetched {len(fileids)} curseforge fileids from queue')

    for i in range(0, len(fileids), CURSEFORGE_LIMIT_SIZE):
        chunk = fileids[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_files(fileIds=chunk)
        available_modids.extend([file["modId"] for file in info])
    return list(set(available_modids))


# check curseforge_fingerprints queue
def check_curseforge_fingerprints_available():
    """
    返回对应的 modids
    """
    available_modids = []
    fingerprints = fetch_curseforge_fingerprints_queue()
    log.info(f'Fetched {len(fingerprints)} curseforge fingerprints from queue')

    for i in range(0, len(fingerprints), CURSEFORGE_LIMIT_SIZE):
        chunk = fingerprints[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_fingerprints(fingerprints=chunk)
        available_modids.extend(
            [fingerprint["file"]["modId"] for fingerprint in info["exactMatches"]]
        )
    return list(set(available_modids))

def check_new_modids(modids: List[int]) -> List[int]:
    """
    返回对应的 modids
    """
    find_result = raw_mongo_client["curseforge_mods"].find({"_id": {"$in": modids}}, {"_id": 1})
    found_modids = [mod["_id"] for mod in find_result]
    return list(set(modids) - set(found_modids))

def check_new_project_ids(project_ids: List[str]) -> List[str]:
    """
    返回对应的 project_ids
    """
    find_result = raw_mongo_client["modrinth_projects"].find({"_id": {"$in": project_ids}}, {"_id": 1})
    found_project_ids = [project["_id"] for project in find_result]
    return list(set(project_ids) - set(found_project_ids))