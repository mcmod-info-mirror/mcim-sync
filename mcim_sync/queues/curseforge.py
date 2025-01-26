from typing import Union, List, Set
from odmantic import query


from mcim_sync.database._redis import sync_redis_engine
from mcim_sync.utils.loger import log
from mcim_sync.config import Config

config = Config.load()

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