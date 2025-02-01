"""
拉取 Modrinth 信息

version 信息包含了 file 信息，所以拉取 version 信息时，会拉取 version 下的所有 file 信息

sync_project 只刷新 project 信息，不刷新 project 下的 version 信息

刷新 project 信息后，会刷新 project 下的所有 version 信息，以及 version 下的所有 file 信息，不刷新 project 自身信息
"""

from typing import List, Optional, Union
from odmantic import query
import json
import time

from mcim_sync.models.database.modrinth import (
    Project,
    File,
    Version,
    Category,
    Loader,
    GameVersion,
)
from mcim_sync.models.database.file_cdn import File as FileCDN
from mcim_sync.utils.constans import ProjectDetail
from mcim_sync.utils.network import request
from mcim_sync.exceptions import ResponseCodeException
from mcim_sync.config import Config
from mcim_sync.database.mongodb import sync_mongo_engine as mongodb_engine
from mcim_sync.utils.model_submitter import ModelSubmitter
from mcim_sync.utils.loger import log


config = Config.load()

API = config.modrinth_api
MAX_LENGTH = config.max_file_size


def sync_project_all_version(
    project_id: str,
    slug: str,
    need_to_cache: bool = True,
) -> int:
    if not slug:
        project = mongodb_engine.find_one(Project, Project.id == project_id)
        if project:
            slug = project.slug
        else:
            raise Exception(f"Slug is required when project not in database")

    try:
        res = request(f"{API}/v2/project/{project_id}/version").json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            return
    except Exception as e:
        log.error(f"Failed to sync project {project_id} versions info: {e}")
        return
    latest_version_id_list = []
    with ModelSubmitter() as submitter:
        for version in res:
            latest_version_id_list.append(version["id"])
            for file in version["files"]:
                file["version_id"] = version["id"]
                file["project_id"] = version["project_id"]
                file_model = File(slug=slug, **file)
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
                        file_model.file_cdn_cached = (
                            True  # 在这里设置 file_cdn_cached，默认为 False
                        )
                submitter.add(file_model)
            submitter.add(Version(slug=slug, **version))
        # delete not found versions
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


def sync_project(project_id: str) -> ProjectDetail:
    try:
        with ModelSubmitter() as submitter:
            res = request(f"{API}/v2/project/{project_id}").json()
            project_model = Project(**res)
            submitter.add(project_model)
            # models.append(project_model)
            # db_project = mongodb_engine.find_one(Project, Project.id == project_id)
            # if db_project is not None:
            #     # check updated
            #     if db_project.updated != res["updated"]:
            #         models.append(Project(**res))
            #         sync_project_all_version(project_id, slug=res["slug"])
            #     else:
            #         return
            total_count = sync_project_all_version(
                project_id,
                slug=res["slug"],
                need_to_cache=project_model.project_type == "mod",
            )
            return ProjectDetail(
                id=project_id, name=res["slug"], version_count=total_count
            )
    except ResponseCodeException as e:
        if e.status_code == 404:
            # models.append(Project(id=project_id, slug=project_id))
            log.error(f"Project {project_id} not found!")
    except Exception as e:
        log.error(f"Failed to sync project {project_id} info: {e}")
        return


def fetch_mutil_projects_info(project_ids: List[str]):
    try:
        res = request(
            f"{API}/v2/projects", params={"ids": json.dumps(project_ids)}
        ).json()
        return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            return []
    except Exception as e:
        log.error(f"Failed to fetch projects info: {e}")
        return []


def fetch_multi_versions_info(version_ids: List[str]):
    try:
        res = request(
            f"{API}/v2/versions", params={"ids": json.dumps(version_ids)}
        ).json()
        return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            return []
    except Exception as e:
        log.error(f"Failed to fetch versions info: {e}")
        return []


def fetch_multi_hashes_info(hashes: List[str], algorithm: str):
    try:
        res = request(
            method="POST",
            url=f"{API}/v2/version_files",
            json={"hashes": hashes, "algorithm": algorithm},
        ).json()
        return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            return {}
    except Exception as e:
        log.error(f"Failed to fetch hashes info: {e}")
        return {}


def sync_categories():
    mongodb_engine.remove(Category)
    with ModelSubmitter() as submitter:
        categories = request(f"{API}/v2/tag/category").json()
        for category in categories:
            submitter.add(Category(**category))
    return categories


def sync_loaders():
    mongodb_engine.remove(Loader)
    with ModelSubmitter() as submitter:
        loaders = request(f"{API}/v2/tag/loader").json()
        for loader in loaders:
            submitter.add(Loader(**loader))
    return loaders


def sync_game_versions():
    mongodb_engine.remove(GameVersion)
    with ModelSubmitter() as submitter:
        game_versions = request(f"{API}/v2/tag/game_version").json()
        for game_version in game_versions:
            submitter.add(GameVersion(**game_version))
    return game_versions
