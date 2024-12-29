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

from models.database.modrinth import Project, File, Version
from models.database.file_cdn import File as FileCDN
from utils.network import request_sync
from exceptions import ResponseCodeException
from config import Config
from database.mongodb import sync_mongo_engine as mongodb_engine
from utils import submit_models
from utils.loger import log
from utils.telegram import ProjectDetail

config = Config.load()

API = config.modrinth_api
MAX_LENGTH = config.max_file_size


def sync_project_all_version(
    project_id: str,
    slug: Optional[str] = None,
) -> List[Union[Project, File, Version]]:
    models = []
    if not slug:
        project = mongodb_engine.find_one(Project, Project.id == project_id)
        if project:
            slug = project.slug
        else:
            try:
                res = request_sync(f"{API}/project/{project_id}").json()
            except ResponseCodeException as e:
                if e.status_code == 404:
                    models.append(Project(found=False, id=project_id, slug=project_id))
                    return
            slug = res["slug"]
    try:
        res = request_sync(f"{API}/project/{project_id}/version").json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            models.append(Project(found=False, id=project_id, slug=project_id))
            return
    except Exception as e:
        log.error(f"Failed to sync project {project_id} versions info: {e}")
        return
    latest_version_id_list = []
    for version in res:
        latest_version_id_list.append(version["id"])
        for file in version["files"]:
            file["version_id"] = version["id"]
            file["project_id"] = version["project_id"]
            file_model = File(found=True, slug=slug, **file)
            if (
                file_model.size <= MAX_LENGTH
                and file_model.filename
                and file_model.url
                and file_model.hashes.sha1
            ):
                models.append(
                    FileCDN(
                        url=file_model.url,
                        sha1=file_model.hashes.sha1,
                        size=file_model.size,
                        mtime=int(time.time()),
                        path=file_model.hashes.sha1,
                    )
                )
            models.append(file_model)
            if len(models) >= 100:
                submit_models(models)
                models = []
        models.append(Version(found=True, slug=slug, **version))
    submit_models(models)
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

def sync_project(project_id: str):
    models = []
    try:
        res = request_sync(f"{API}/project/{project_id}").json()
        models.append(Project(found=True, **res))
        # db_project = mongodb_engine.find_one(Project, Project.id == project_id)
        # if db_project is not None:
        #     # check updated
        #     if db_project.updated != res["updated"]:
        #         models.append(Project(found=True, **res))
        #         sync_project_all_version(project_id, slug=res["slug"])
        #     else:
        #         return
        total_count = sync_project_all_version(project_id, slug=res["slug"])
    except ResponseCodeException as e:
        if e.status_code == 404:
            models = [Project(found=False, id=project_id, slug=project_id)]
    except Exception as e:
        log.error(f"Failed to sync project {project_id} info: {e}")
        return
    submit_models(models)
    return ProjectDetail(id=project_id, name=res["slug"], version_count=total_count)


def fetch_mutil_projects_info(project_ids: List[str]):
    try:
        res = request_sync(
            f"{API}/projects", params={"ids": json.dumps(project_ids)}
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
        res = request_sync(
            f"{API}/versions", params={"ids": json.dumps(version_ids)}
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
        res = request_sync(
            method="POST",
            url=f"{API}/version_files",
            json={"hashes": hashes, "algorithm": algorithm},
        ).json()
        return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            return {}
    except Exception as e:
        log.error(f"Failed to fetch hashes info: {e}")
        return {}
