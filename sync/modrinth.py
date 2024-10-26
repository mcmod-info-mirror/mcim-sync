"""
拉取 Modrinth 信息

version 信息包含了 file 信息，所以拉取 version 信息时，会拉取 version 下的所有 file 信息

sync_project 只刷新 project 信息，不刷新 project 下的 version 信息

刷新 project 信息后，会刷新 project 下的所有 version 信息，以及 version 下的所有 file 信息，不刷新 project 自身信息

同步逻辑：
1. 刷新 project | 触发条件: project 不存在或已经过期 -> sync_project -> 刷新 project 下的所有 version -> 刷新 project 下的所有 File

2. 刷新 version | 触发条件: version 不存在或已经过期 -> sync_version -> 刷新 version 下的 File -> 刷新 project 下的所有 version

3. 刷新 hash | 触发条件: hash 不存在 -> sync_hash -> 刷新 hash 下的 File -> 刷新 project 下的所有 version
"""

from typing import List, Optional, Union
import json
import os
import time
import httpx
from datetime import datetime
from odmantic import query

from models.database.modrinth import Project, File, Version
from models.database.file_cdn import File as FileCDN
from utils.network import request_sync
from exceptions import ResponseCodeException
from config import MCIMConfig
from database.mongodb import sync_mongo_engine as mongodb_engine

from utils.loger import log

mcim_config = MCIMConfig.load()

API = mcim_config.modrinth_api
MAX_LENGTH = mcim_config.max_file_size


def submit_models(models: List[Union[Project, File, Version]]):
    log.debug(f"Submited: {len(models)}")
    mongodb_engine.save_all(models)



# limit decorator
def limit(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

def check_alive():
    res = request_sync("https://api.modrinth.com")
    return res.json()


def sync_project_all_version(
    project_id: str,
    slug: Optional[str] = None,
    verify_expire: bool = False,
) -> List[Union[Project, File, Version]]:
    if not verify_expire:
        project: Optional[Project] = mongodb_engine.find_one(
            Project, Project.id == project_id
        )
        if project:
            if (
                time.time()
                <= project.sync_at.timestamp()
                + mcim_config.expire_second.modrinth.project
            ):
                log.info(f"Project {project_id} is not expired, pass!")
                return
            elif not slug:
                slug = project.slug

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
    for version in res:
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


def sync_multi_projects_all_version(
    project_ids: List[str],
    slugs: Optional[dict] = None,
    # ) -> List[Union[Project, File, Version]]:
) -> None:
    mod_models: Optional[List[Project]] = mongodb_engine.find(
        Project, query.in_(Project.id, project_ids)
    )
    if mod_models:
        for model in mod_models:
            if (
                time.time()
                <= model.sync_at.timestamp()
                + mcim_config.expire_second.modrinth.project
            ):
                project_ids.remove(model.id)
                log.info(f"Project {model.id} is not expired, pass!")

    for project_id in project_ids:
        sync_project_all_version(
            project_id, slug=slugs[project_id] if slugs else None, verify_expire=True
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


def sync_multi_projects(project_ids: List[str]):
    try:
        res = request_sync(
            f"{API}/projects", params={"ids": json.dumps(project_ids)}
        ).json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            models = []
            for project_id in project_ids:
                models.append(Project(found=False, id=project_id, slug=project_id))
            submit_models(models)
            return
    db_projects = mongodb_engine.find(Project, query.in_(Project.id, project_ids))
    temp_db_projects_updated = {}
    for db_project in db_projects:
        temp_db_projects_updated[db_project.id] = db_project.updated
    for project_res in res:
        if project_res["id"] in temp_db_projects_updated:
            if temp_db_projects_updated[project_res["id"]] == project_res["updated"]:
                project_ids.remove(project_res["id"])
                log.info(f"Project {project_res['id']} is not out-of-date, pass!")

    models = []
    slugs = {}
    for project_res in res:
        slugs[project_res["id"]] = project_res["slug"]
        models.append(Project(found=True, **project_res))
    sync_multi_projects_all_version(project_ids, slugs=slugs)
    submit_models(models)


def process_version_resp(res: dict) -> List[Union[Project, File, Version]]:
    models = []
    for file in res["files"]:
        file["version_id"] = res["id"]
        file["project_id"] = res["project_id"]
        models.append(File(found=True, **file))
    models.append(Version(found=True, **res))
    return models



def sync_version(version_id: str):
    try:
        res = request_sync(f"{API}/version/{version_id}").json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            models = [Version(found=False, id=version_id)]
            # submit_models(models)
            return
    sync_project_all_version(res["project_id"])


def process_multi_versions(res: List[dict]):
    models = []
    for version in res:
        for file in version["files"]:
            file["version_id"] = version["id"]
            file["project_id"] = res["project_id"]
            models.append(File(found=True, **file))
        models.append(Version(found=True, **version))
    return models

def sync_multi_versions(version_ids: List[str]):
    try:
        res = request_sync(
            f"{API}/versions", params={"ids": json.dumps(version_ids)}
        ).json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            models = []
            for version_id in version_ids:
                models.append(Version(found=False, id=version_id))
            submit_models(models)
            return
    project_ids = list(set([version["project_id"] for version in res]))  # 去重
    sync_multi_projects_all_version(project_ids)


def sync_hash(hash: str, algorithm: str):
    try:
        res = request_sync(
            f"{API}/version_file/{hash}", params={"algorithm": algorithm}
        ).json()
    except ResponseCodeException as e:
        # if e.status_code == 404:
        #     models = [File(found=False, hash=hash)]
        #     submit_models(models)
        #     return
        return
    sync_project_all_version(res["project_id"])


def process_multi_hashes(res: dict):
    models = []
    for version in res.values():
        for file in version["files"]:
            file["version_id"] = version["id"]
            file["project_id"] = version["project_id"]
            models.append(File(found=True, **file))
        models.append(Version(found=True, **version))
    return models



def sync_multi_hashes(hashes: List[str], algorithm: str):
    try:
        res = request_sync(
            method="POST",
            url=f"{API}/version_files",
            json={"hashes": hashes, "algorithm": algorithm},
        ).json()
    except ResponseCodeException as e:
        # if e.status_code == 404:
        #     models = []
        #     for hash in hashes:
        #         models.append(File(found=False, hash=hash))
        #     submit_models(models)
        return
    # models = []
    # models.extend(process_multi_hashes(res))
    sync_multi_projects_all_version([version["project_id"] for version in res.values()])
    # submit_models(models)

def fetch_mutil_projects_info(project_ids: List[str]):
    try:
        res = request_sync(
            f"{API}/projects", params={"ids": json.dumps(project_ids)}
        ).json()
    except ResponseCodeException as e:
        if e.status_code == 404:
            return []
    return res


# def sync_tags():
#     # db 1
#     categories = request_sync(f"{API}/tag/category").json()
#     loaders = request_sync(f"{API}/tag/loader").json()
#     game_versions = request_sync(f"{API}/tag/game_version").json()
#     donation_platform = request_sync(f"{API}/tag/donation_platform").json()
#     project_type = request_sync(f"{API}/tag/project_type").json()
#     side_type = request_sync(f"{API}/tag/side_type").json()

#     redis_engine.hset("modrinth", "categories", json.dumps(categories))
#     redis_engine.hset("modrinth", "loaders", json.dumps(loaders))
#     redis_engine.hset("modrinth", "game_versions", json.dumps(game_versions))
#     redis_engine.hset("modrinth", "donation_platform", json.dumps(donation_platform))
#     redis_engine.hset("modrinth", "project_type", json.dumps(project_type))
#     redis_engine.hset("modrinth", "side_type", json.dumps(side_type))