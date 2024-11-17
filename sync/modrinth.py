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

from utils.loger import log

config = Config.load()

API = config.modrinth_api
MAX_LENGTH = config.max_file_size


def submit_models(models: List[Union[Project, File, Version]]):
    if len(models) != 0:
        log.debug(f"Submited models: {len(models)}")
        mongodb_engine.save_all(models)


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
        query.and_(
            query.not_in(Version.id, latest_version_id_list),
            Version.project_id == project_id,
        ),
    )
    log.info(
        f"Finished sync project {project_id} versions info, total {len(res)} versions, removed {removed_count} versions"
    )


def sync_project(project_id: str):
    models = []
    try:
        res = request_sync(f"{API}/project/{project_id}").json()
        models.append(Project(found=True, **res))
        db_project = mongodb_engine.find_one(Project, Project.id == project_id)
        if db_project is not None:
            # check updated
            if db_project.updated != res["updated"]:
                models.append(Project(found=True, **res))
                sync_project_all_version(project_id, slug=res["slug"])
            else:
                return
    except ResponseCodeException as e:
        if e.status_code == 404:
            models = [Project(found=False, id=project_id, slug=project_id)]
    submit_models(models)


def fetch_mutil_projects_info(project_ids: List[str]):
    try:
        res = request_sync(
            f"{API}/projects", params={"ids": json.dumps(project_ids)}
        ).json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            return []
    return res
