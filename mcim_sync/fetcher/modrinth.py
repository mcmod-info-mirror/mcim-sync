from typing import Union, List, Set
from odmantic import query
import datetime
import time

from mcim_sync.database.mongodb import sync_mongo_engine, raw_mongo_client
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.modrinth import Project
from mcim_sync.checker.modrinth import check_modrinth_data_updated

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
        time.sleep(MODRINTH_DELAY)
        log.debug(f"Delay {MODRINTH_DELAY} seconds")
    return result



def fetch_expired_modrinth_data() -> List[str]:
    expired_project_ids = set()
    skip = 0
    while True:
        projects_result: List[Project] = list(
            sync_mongo_engine.find(Project, skip=skip, limit=MODRINTH_LIMIT_SIZE)
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
