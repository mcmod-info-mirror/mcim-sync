from typing import List

from mcim_sync.database.mongodb import raw_mongo_client
from mcim_sync.utils.loger import log
from mcim_sync.config import Config

config = Config.load()

def remove_project(project_id: str):
    project_result = raw_mongo_client["modrinth_projects"].delete_one({"_id": project_id})
    version_result = raw_mongo_client["modrinth_versions"].delete_many({"project_id": project_id})
    hash_result = raw_mongo_client["modrinth_hashes"].delete_many({"project_id": project_id})
    log.debug(f"Remove project {project_id}, {version_result.deleted_count} versions, {hash_result.deleted_count} hashes")
    return project_result, version_result, hash_result

def remove_projects(project_ids: List[str]):
    result = []
    for project_id in project_ids:
        singal_result = remove_project(project_id)
        if singal_result[0].deleted_count == 0 and singal_result[1].deleted_count == 0 and singal_result[2].deleted_count == 0:
            log.debug(f"Can't remove project {project_id}, not found")
            continue
        result.append({
            "project_id": project_id,
            "version_count": singal_result[1].deleted_count,
            "hash_count": singal_result[2].deleted_count
        })
        log.debug(f"Remove project {project_id}, {singal_result[1].deleted_count} versions, {singal_result[2].deleted_count} hashes")
    return result