"""
拉取 Modrinth 信息

version 信息包含了 file 信息，所以拉取 version 信息时，会拉取 version 下的所有 file 信息

sync_project 只刷新 project 信息，不刷新 project 下的 version 信息

刷新 project 信息后，会刷新 project 下的所有 version 信息，以及 version 下的所有 file 信息，不刷新 project 自身信息
"""

from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Optional, Union
from odmantic import query
import time

from mcim_sync.models.database.modrinth import (
    Project,
    File,
    Version,
    Category,
    Loader,
    GameVersion,
)
from mcim_sync.apis.modrinth import (
    get_project,
    get_project_all_version,
    get_categories,
    get_loaders,
    get_game_versions,
    get_mutil_projects_info,
    get_multi_hashes_info,
    get_multi_versions_info,
    get_search_result,
)
from mcim_sync.models.database.file_cdn import File as FileCDN
from mcim_sync.utils.constans import ProjectDetail
from mcim_sync.exceptions import ResponseCodeException
from mcim_sync.config import Config
from mcim_sync.database.mongodb import sync_mongo_engine as mongodb_engine
from mcim_sync.utils.model_submitter import ModelSubmitter
from mcim_sync.utils.loger import log


config = Config.load()

API = config.modrinth_api
MAX_LENGTH = config.max_file_size


def sync_project_all_version(project_id: str, need_to_cache: bool = True) -> int:
    res = get_project_all_version(project_id)
    latest_version_id_list = []

    with ModelSubmitter() as submitter:
        for version in res:
            latest_version_id_list.append(version["id"])
            for file in version["files"]:
                file["version_id"] = version["id"]
                file["project_id"] = version["project_id"]
                file_model = File(**file)
                if config.file_cdn:
                    if (
                        need_to_cache
                        and file_model.size <= MAX_LENGTH
                        and file_model.filename
                        and file_model.url
                        and file_model.hashes.sha1
                    ):
                        submitter.add(
                            FileCDN(
                                url=file_model.url,
                                sha1=file_model.hashes.sha1,
                                size=file_model.size,
                                mtime=int(time.time()),
                                path=file_model.hashes.sha1,
                            )  # type: ignore
                        )
                        file_model.file_cdn_cached = True
                submitter.add(file_model)
            submitter.add(Version(**version))

        removed_count = mongodb_engine.remove(
            Version,
            query.not_in(Version.id, latest_version_id_list),
            Version.project_id == project_id,
        )
        total_count = len(res)
        log.info(
            f"Finished sync project {project_id} versions info, total {total_count} versions, removed {removed_count} versions"
        )
        return total_count


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_project(project_id: str) -> Optional[ProjectDetail]:
    try:
        res = get_project(project_id)
        with ModelSubmitter() as submitter:
            project_model = Project(**res)
            submitter.add(project_model)
            total_count = sync_project_all_version(
                project_id,
                need_to_cache=project_model.project_type == "mod",
            )
            return ProjectDetail(
                id=project_id, name=res["slug"], version_count=total_count
            )
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error(f"Project {project_id} not found")
            return None
        else:
            raise e


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_categories() -> List[dict]:
    mongodb_engine.remove(Category)
    with ModelSubmitter() as submitter:
        categories = get_categories()
        for category in categories:
            submitter.add(Category(**category))
    return categories


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_loaders() -> List[dict]:
    mongodb_engine.remove(Loader)
    with ModelSubmitter() as submitter:
        loaders = get_loaders()
        for loader in loaders:
            submitter.add(Loader(**loader))
    return loaders


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_game_versions() -> List[dict]:
    mongodb_engine.remove(GameVersion)
    with ModelSubmitter() as submitter:
        game_versions = get_game_versions()
        for game_version in game_versions:
            submitter.add(GameVersion(**game_version))
    return game_versions


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_mutil_projects_info(project_ids: List[str]) -> Optional[List[dict]]:
    try:
        res = get_mutil_projects_info(project_ids)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil projects info: {e}")
        return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_multi_hashes_info(hashes: List[str], algorithm: str) -> Optional[dict]:
    try:
        res = get_multi_hashes_info(hashes, algorithm)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil hashes info: {e}")
        return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_multi_versions_info(version_ids: List[str]) -> Optional[List[dict]]:
    try:
        res = get_multi_versions_info(version_ids)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil versions info: {e}")
        return None
    
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_search_result(
    query: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
    facets: Optional[str] = None,
    index: Optional[str] = None,
) -> Optional[dict]:
    try:
        res = get_search_result(query, offset, limit, facets, index)
        return res
    except Exception as e:
        log.error(f"Failed to fetch search result: {e}")
        return None