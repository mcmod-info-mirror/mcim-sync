from typing import Union, List, Set, Tuple
import datetime

from mcim_sync.database.mongodb import raw_mongo_client
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




def check_modrinth_data_updated_and_alive(
    projects: List[Project],
) -> Tuple[Set[str], Set[str]]:
    local_project_info = {
        project.id: {
            "updated": project.updated.replace(tzinfo=None),
            "versions": project.versions,
            "game_versions": project.game_versions,
        }
        for project in projects
    }

    all_project_ids = list(local_project_info.keys())
    outdated_ids: Set[str] = set()
    alive_ids: Set[str] = set()

    remote_projects = fetch_mutil_projects_info(project_ids=all_project_ids)

    if remote_projects is None:
        return set(), set()

    with ModelSubmitter() as submitter:
        for remote in remote_projects:
            project_id = remote["id"]
            alive_ids.add(project_id)

            local = local_project_info[project_id]

            local_updated = local["updated"]
            remote_updated = datetime.datetime.fromisoformat(remote["updated"]).replace(
                tzinfo=None
            )

            local_versions = local["versions"]
            remote_versions = remote["versions"]

            local_game_versions = local["game_versions"]
            remote_game_versions = remote["game_versions"]

            if _is_project_updated(
                local_updated, remote_updated
            ):  # Check if project is updated
                outdated_ids.add(project_id)
                log.debug(f"[{project_id}] Updated: {local_updated} → {remote_updated}")
            elif _has_versions_changed(
                local_versions, remote_versions
            ):  # Check if versions have changed
                outdated_ids.add(project_id)
                diff_versions = set(remote_versions) ^ set(local_versions)
                if diff_versions:
                    log.debug(
                        f"[{project_id}] Version {diff_versions} mismatch, needs sync."
                    )
            elif _has_game_versions_changed(
                local_game_versions, remote_game_versions
            ):  # Check if game versions have changed
                outdated_ids.add(project_id)
                diff_game_versions = set(remote_game_versions) ^ set(
                    local_game_versions
                )
                if diff_game_versions:
                    log.debug(
                        f"[{project_id}] Game versions {diff_game_versions} changed, needs sync."
                    )
            else:
                log.trace(f"[{project_id}] No change, skipping.")

            submitter.add(Project(**remote))

    dead_ids = set(all_project_ids) - alive_ids

    log.debug(f"Outdated projects: {len(outdated_ids)}, Dead projects: {len(dead_ids)}")

    return outdated_ids, dead_ids


def _is_project_updated(local: datetime.datetime, remote: datetime.datetime) -> bool:
    return int(local.timestamp()) != int(remote.timestamp())


def _has_versions_changed(
    local_versions: List[str], remote_versions: List[str]
) -> bool:
    return local_versions != remote_versions


def _has_game_versions_changed(
    local_game_versions: List[str], remote_game_versions: List[str]
) -> bool:
    return local_game_versions != remote_game_versions


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
                available_project_ids.extend(
                    [hash["project_id"] for hash in info.values()]
                )
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
    limit = 100

    while True:
        res = fetch_search_result(offset=offset, index="newest", limit=limit)
        if not res or not res["hits"] or len(res["hits"]) == 0:
            break

        temp_project_ids = [project["project_id"] for project in res["hits"]]

        # Check which projects are already in database
        existing_projects = set(
            doc["_id"]
            for doc in raw_mongo_client["modrinth_projects"].find(
                {"_id": {"$in": temp_project_ids}}, {"_id": 1}
            )
        )

        # If we found any existing project, stop searching
        if existing_projects:
            new_ids = [pid for pid in temp_project_ids if pid not in existing_projects]
            new_project_ids.extend(new_ids)
            break

        # If all projects are new, add them and continue searching
        new_project_ids.extend(temp_project_ids)
        log.debug(f"Found {len(temp_project_ids)} new project IDs at offset {offset}")

        offset += limit

    return new_project_ids
