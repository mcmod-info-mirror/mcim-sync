from typing import Union, List, Set
from odmantic import query


from database._redis import sync_redis_engine
from utils.loger import log
from config import Config

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

def fetch_curseforge_modids_queue() -> List[int]:
    if sync_redis_engine.exists("curseforge_modids") == 0:
        return []
    modids: List[bytes] = sync_redis_engine.smembers("curseforge_modids")
    if modids:
        modids = [int(modid.decode("utf-8")) for modid in modids]
    return modids

def fetch_curseforge_fileids_queue() -> List[int]:
    if sync_redis_engine.exists("curseforge_fileids") == 0:
        return []
    fileids: List[bytes] = sync_redis_engine.smembers("curseforge_fileids")
    if fileids:
        fileids = [int(fileid.decode("utf-8")) for fileid in fileids]
    return fileids

def fetch_curseforge_fingerprints_queue() -> List[int]:
    if sync_redis_engine.exists("curseforge_fingerprints") == 0:
        return []
    fingerprints: List[bytes] = sync_redis_engine.smembers("curseforge_fingerprints")
    if fingerprints:
        fingerprints = [
            int(fingerprint.decode("utf-8")) for fingerprint in fingerprints
        ]
    return fingerprints

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

def clear_curseforge_modids_queue():
    sync_redis_engine.delete("curseforge_modids")

def clear_curseforge_fileids_queue():
    sync_redis_engine.delete("curseforge_fileids")

def clear_curseforge_fingerprints_queue():
    sync_redis_engine.delete("curseforge_fingerprints")

def clear_curseforge_all_queues():
    clear_curseforge_modids_queue()
    clear_curseforge_fileids_queue()
    clear_curseforge_fingerprints_queue()