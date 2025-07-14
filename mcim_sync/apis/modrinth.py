from typing import List, Optional
import json

from mcim_sync.utils.network import request
from mcim_sync.config import Config

config = Config.load()
API = config.modrinth_api


def get_project_all_version(
    project_id: str
) -> List[dict]:
    res = request(f"{API}/v2/project/{project_id}/version").json()
    return res

def get_project(project_id: str) -> dict:
    res = request(f"{API}/v2/project/{project_id}").json()
    return res

def get_mutil_projects_info(project_ids: List[str]) -> List[dict]:
    res = request(f"{API}/v2/projects", params={"ids": json.dumps(project_ids)}).json()
    return res


def get_multi_versions_info(version_ids: List[str]) -> List[dict]:
    res = request(f"{API}/v2/versions", params={"ids": json.dumps(version_ids)}).json()
    return res


def get_multi_hashes_info(hashes: List[str], algorithm: str) -> dict:
    res = request(
        method="POST",
        url=f"{API}/v2/version_files",
        json={"hashes": hashes, "algorithm": algorithm},
    ).json()
    return res


def get_categories() -> List[dict]:
    res = request(f"{API}/v2/tag/category").json()
    return res


def get_loaders() -> List[dict]:
    res = request(f"{API}/v2/tag/loader").json()
    return res


def get_game_versions() -> List[dict]:
    res = request(f"{API}/v2/tag/game_version").json()
    return res

def get_search_result(
    query: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
    facets: Optional[str] = None,
    index: Optional[str] = None,
) -> dict:
    params = {
        "query": query,
        "offset": offset,
        "limit": limit,
        "facets": facets,
        "index": index,
    }
    res = request(f"{API}/v2/search", params=params).json()
    return res