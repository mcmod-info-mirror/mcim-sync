from typing import List

from mcim_sync.database._redis import sync_redis_engine
from mcim_sync.config import Config

config = Config.load()
def fetch_modrinth_project_ids_queue() -> List[str]:
    if sync_redis_engine.exists("modrinth_project_ids") == 0:
        return []
    project_ids: List[bytes] = sync_redis_engine.smembers("modrinth_project_ids")
    if project_ids:
        project_ids = [project_id.decode("utf-8") for project_id in project_ids]
    return project_ids

def fetch_modrinth_version_ids_queue() -> List[str]:
    if sync_redis_engine.exists("modrinth_version_ids") == 0:
        return []
    version_ids: List[bytes] = sync_redis_engine.smembers("modrinth_version_ids")
    if version_ids:
        version_ids = [version_id.decode("utf-8") for version_id in version_ids]
    return version_ids

def fetch_modrinth_hashes_queue(algorithm: str) -> List[str]:
    if sync_redis_engine.exists(f"modrinth_hashes_{algorithm}") == 0:
        return []
    hashes: List[bytes] = sync_redis_engine.smembers(f"modrinth_hashes_{algorithm}")
    if hashes:
        hashes = [hash.decode("utf-8") for hash in hashes]
    return hashes

def clear_modrinth_project_ids_queue():
    sync_redis_engine.delete("modrinth_project_ids")

def clear_modrinth_version_ids_queue():
    sync_redis_engine.delete("modrinth_version_ids")

def clear_modrinth_hashes_queue(algorithm: str):
    sync_redis_engine.delete(f"modrinth_hashes_{algorithm}")

def clear_modrinth_all_queues():
    clear_modrinth_project_ids_queue()
    clear_modrinth_version_ids_queue()
    clear_modrinth_hashes_queue("sha1")
    clear_modrinth_hashes_queue("sha512")