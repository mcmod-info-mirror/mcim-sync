from typing import List, Optional, Union
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
    # latest_version_id_list = []

    # with ModelSubmitter() as submitter:
    #     for version in res:
    #         latest_version_id_list.append(version["id"])
    #         for file in version["files"]:
    #             file["version_id"] = version["id"]
    #             file["project_id"] = version["project_id"]
    #             file_model = File(**file)
    #             if config.file_cdn:
    #                 if (
    #                     need_to_cache
    #                     and file_model.size <= MAX_LENGTH
    #                     and file_model.filename
    #                     and file_model.url
    #                     and file_model.hashes.sha1
    #                 ):
    #                     submitter.add(
    #                         FileCDN(
    #                             url=file_model.url,
    #                             sha1=file_model.hashes.sha1,
    #                             size=file_model.size,
    #                             mtime=int(time.time()),
    #                             path=file_model.hashes.sha1,
    #                         ) # type: ignore
    #                     )
    #                     file_model.file_cdn_cached = True
    #             submitter.add(file_model)
    #         submitter.add(Version(**version))

    #     removed_count = mongodb_engine.remove(
    #         Version,
    #         query.not_in(Version.id, latest_version_id_list),
    #         Version.project_id == project_id,
    #     )
    #     total_count = len(res)
    #     log.info(
    #         f"Finished sync project {project_id} versions info, total {total_count} versions, removed {removed_count} versions"
    #     )
    #     return total_count


def get_project(project_id: str) -> dict:
    res = request(f"{API}/v2/project/{project_id}").json()
    # with ModelSubmitter() as submitter:
    #     project_model = Project(**res)
    #     submitter.add(project_model)
    #     total_count = get_project_all_version(
    #         project_id,
    #         need_to_cache=project_model.project_type == "mod",
    #     )
    #     return ProjectDetail(id=project_id, name=res["slug"], version_count=total_count)

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
    # mongodb_engine.remove(Category)
    # with ModelSubmitter() as submitter:
    #     categories = request(f"{API}/v2/tag/category").json()
    #     for category in categories:
    #         submitter.add(Category(**category))
    # return categories
    res = request(f"{API}/v2/tag/category").json()
    return res


def get_loaders() -> List[dict]:
    # mongodb_engine.remove(Loader)
    # with ModelSubmitter() as submitter:
    #     loaders = request(f"{API}/v2/tag/loader").json()
    #     for loader in loaders:
    #         submitter.add(Loader(**loader))
    # return loaders
    res = request(f"{API}/v2/tag/loader").json()
    return res


def get_game_versions() -> List[dict]:
    # mongodb_engine.remove(GameVersion)
    # with ModelSubmitter() as submitter:
    #     game_versions = request(f"{API}/v2/tag/game_version").json()
    #     for game_version in game_versions:
    #         submitter.add(GameVersion(**game_version))
    # return game_versions
    res = request(f"{API}/v2/tag/game_version").json()
    return res
