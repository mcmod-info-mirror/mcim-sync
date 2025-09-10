from typing import Union, List
import datetime
import time

from mcim_sync.database.mongodb import sync_mongo_engine
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.modrinth import Project
from mcim_sync.checker.modrinth import check_modrinth_data_updated_and_alive

config = Config.load()


MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size
MAX_WORKERS: int = config.max_workers

MODRINTH_DELAY: Union[float, int] = config.modrinth_delay




def fetch_all_modrinth_data() -> List[str]:
    skip = 0
    result = []
    while True:
        projects_result: List[Project] = list(
            sync_mongo_engine.find(Project, skip=skip, limit=MODRINTH_LIMIT_SIZE)
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        result.extend([project.id for project in projects_result])
        # time.sleep(MODRINTH_DELAY)
        # log.debug(f"Delay {MODRINTH_DELAY} seconds")
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
                # skip=skip, limit=MODRINTH_LIMIT_SIZE
                query,
                skip=skip,
                limit=MODRINTH_LIMIT_SIZE,
            )
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        result.extend([project.id for project in projects_result])
        # time.sleep(MODRINTH_DELAY)
        # log.debug(f"Delay {MODRINTH_DELAY} seconds")
    return result



def fetch_expired_and_removed_modrinth_data() -> tuple[List[str], List[str]]:
    expired_project_ids = set()
    removed_project_ids = set()
    skip = 0
    while True:
        projects_result: List[Project] = list(
            sync_mongo_engine.find(Project, skip=skip, limit=MODRINTH_LIMIT_SIZE)
        )
        if not projects_result:
            break
        skip += MODRINTH_LIMIT_SIZE
        result = check_modrinth_data_updated_and_alive(projects_result)
        if result is None:
            continue
        check_expired_result, not_alive_result = result
        expired_project_ids.update(check_expired_result)
        removed_project_ids.update(not_alive_result)
        log.debug(f"Matched {len(check_expired_result)} expired projects, {len(not_alive_result)} removed projects")
        if len(not_alive_result) != 0:
            log.debug(f"Removed project ids: {not_alive_result}")
        time.sleep(MODRINTH_DELAY)
        log.debug(f"Delay {MODRINTH_DELAY} seconds")
    return list(expired_project_ids), list(removed_project_ids)
