from typing import Union, List, Set, Tuple
import datetime
import time

from mcim_sync.database.mongodb import sync_mongo_engine, raw_mongo_client
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.modrinth import Project
from mcim_sync.utils.model_submitter import ModelSubmitter

from mcim_sync.queues.modrinth import (
    fetch_modrinth_project_ids_queue,
    fetch_modrinth_version_ids_queue,
    fetch_modrinth_hashes_queue,
)
from mcim_sync.sync.modrinth import (
    fetch_mutil_projects_info,
    fetch_multi_versions_info,
    fetch_multi_hashes_info,
    fetch_search_result,
)

config = Config.load()

MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size
MAX_WORKERS: int = config.max_workers

MODRINTH_DELAY: Union[float, int] = config.modrinth_delay


def check_modrinth_data_updated_and_alive(projects: List[Project]) -> tuple[set[str], set[str]]:
    project_info = {
        project.id: {"sync_date": project.updated, "versions": project.versions}
        for project in projects
    }
    expired_project_ids: Set[str] = set()
    db_project_ids = [project.id for project in projects]
    alive_project_ids = []
    
    info = fetch_mutil_projects_info(project_ids=db_project_ids)
    
    if info is not None:
        with ModelSubmitter() as submitter:
            for project in info:
                project_id = project["id"]

                # mark as alive
                alive_project_ids.append(project_id)

                submitter.add(Project(**project))

                sync_date: datetime.datetime = project_info[project_id][
                    "sync_date"
                ].replace(tzinfo=None)
                project_info[project_id]["source_date"] = project["updated"]
                updated_date = datetime.datetime.fromisoformat(project["updated"]).replace(
                    tzinfo=None
                )
                if int(sync_date.timestamp()) == int(updated_date.timestamp()):
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
                        f"Project {project_id} is updated {sync_date.isoformat(timespec='seconds')} -> {updated_date.isoformat(timespec='seconds')}!"
                    )

        # check if project is not alive
        not_alive_project_ids = set(db_project_ids) - set(alive_project_ids)

        log.debug(
            f"Expired project ids: {len(expired_project_ids)}, not alive project ids: {len(not_alive_project_ids)}"
        )

        return expired_project_ids, not_alive_project_ids


# check modrinth_project_ids queue
def check_modrinth_project_ids_available():
    """
    返回对应的 project_ids
    """
    available_project_ids = []
    project_ids = fetch_modrinth_project_ids_queue()
    log.info(f"Fetched {len(project_ids)} modrinth project ids from queue")

    for i in range(0, len(project_ids), MODRINTH_LIMIT_SIZE):
        chunk = project_ids[i : i + MODRINTH_LIMIT_SIZE]
        info = fetch_mutil_projects_info(project_ids=chunk)
        if info is not None:
            available_project_ids.extend([project["id"] for project in info])
    return list(set(available_project_ids))


# check modrinth_version_ids queue
def check_modrinth_version_ids_available():
    """
    返回对应的 project_ids
    """
    available_project_ids = []
    version_ids = fetch_modrinth_version_ids_queue()
    log.info(f"Fetched {len(version_ids)} modrinth version ids from queue")

    for i in range(0, len(version_ids), MODRINTH_LIMIT_SIZE):
        chunk = version_ids[i : i + MODRINTH_LIMIT_SIZE]
        info = fetch_multi_versions_info(version_ids=chunk)
        if info is not None:
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
        log.info(f"Fetched {len(hashes)} modrinth hashes from queue")

        for i in range(0, len(hashes), MODRINTH_LIMIT_SIZE):
            chunk = hashes[i : i + MODRINTH_LIMIT_SIZE]
            info = fetch_multi_hashes_info(hashes=chunk, algorithm=algorithm)
            if info is not None:
                available_project_ids.extend([hash["project_id"] for hash in info.values()])
    return list(set(available_project_ids))


def check_new_project_ids(project_ids: List[str]) -> List[str]:
    """
    返回对应的 project_ids
    """
    find_result = raw_mongo_client["modrinth_projects"].find(
        {"_id": {"$in": project_ids}}, {"_id": 1}
    )
    found_project_ids = [project["_id"] for project in find_result]
    return list(set(project_ids) - set(found_project_ids))

def check_newest_search_result() -> List[str]:
    """
    遍历 newest search result 直到出现第一个已缓存的 project_id，然后返回所有 new project_id
    """
    new_project_ids = []
    offset = 0
    flag = True
    while flag:
        res = fetch_search_result(offset=offset, index="newest", limit=100)
        if res is not None:
            if len(res["hits"]) != 0:
                temp_new_project_ids = [project["project_id"] for project in res["hits"]]
                # 查找是否已缓存
                db_result = raw_mongo_client["modrinth_projects"].find({"_id": {"$in": temp_new_project_ids}}, {"_id": 1})
                for project in db_result:
                    if project["_id"] in temp_new_project_ids:
                        temp_new_project_ids.remove(project["_id"])
                        flag = False
                log.debug(
                    f"Fetched {len(temp_new_project_ids)} new project ids from search result, found {len(new_project_ids)} new project ids"
                )
                new_project_ids.extend(temp_new_project_ids)
        offset += 100
    return new_project_ids