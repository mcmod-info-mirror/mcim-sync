from typing import Union, List, Set
from odmantic import query
import datetime
import time

from mcim_sync.database.mongodb import sync_mongo_engine, raw_mongo_client
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.curseforge import Mod
from mcim_sync.sync.curseforge import (
    fetch_mutil_mods_info,
    fetch_mutil_files,
    fetch_mutil_fingerprints,
)
from mcim_sync.queues.curseforge import (
    fetch_curseforge_modids_queue,
    fetch_curseforge_fileids_queue,
    fetch_curseforge_fingerprints_queue,
)
from mcim_sync.utils import ModelSubmitter

config = Config.load()

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size

MAX_WORKERS: int = config.max_workers

CURSEFORGE_DELAY: Union[float, int] = config.curseforge_delay

def check_curseforge_data_updated(mods: List[Mod]) -> Set[int]:
    mod_date = {mod.id: {"sync_date": mod.dateModified} for mod in mods}
    expired_modids: Set[int] = set()
    mod_info = fetch_mutil_mods_info(modIds=[mod.id for mod in mods])
    with ModelSubmitter() as submitter:
        for mod in mod_info:
            submitter.add(Mod(**mod))
            modid = mod["id"]
            mod_date[modid]["source_date"] = mod["dateModified"]
            sync_date: datetime.datetime = mod_date[modid]["sync_date"].replace( # type: ignore
                tzinfo=None
            )
            dateModified_date = datetime.datetime.fromisoformat(
                mod["dateModified"]
            ).replace(tzinfo=None)
            if int(sync_date.timestamp()) == int(dateModified_date.timestamp()):
                log.debug(f"Mod {modid} is not updated, pass!")
            else:
                expired_modids.add(modid)
                log.debug(
                    f"Mod {modid} is updated {sync_date.isoformat(timespec='seconds')} -> {dateModified_date.isoformat(timespec='seconds')}!"
                )

    return expired_modids



# check curseforge_modids queue
def check_curseforge_modids_available():
    """
    返回对应的 modids
    """
    available_modids = []
    modids = fetch_curseforge_modids_queue()
    log.info(f"Fetched {len(modids)} curseforge modids from queue")

    for i in range(0, len(modids), CURSEFORGE_LIMIT_SIZE):
        chunk = modids[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_mods_info(modIds=chunk)
        available_modids.extend([mod["id"] for mod in info])
    return list(set(available_modids))


# check curseforge_fileids queue
def check_curseforge_fileids_available():
    """
    返回对应的 modids
    """
    available_modids = []
    fileids = fetch_curseforge_fileids_queue()
    log.info(f"Fetched {len(fileids)} curseforge fileids from queue")

    for i in range(0, len(fileids), CURSEFORGE_LIMIT_SIZE):
        chunk = fileids[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_files(fileIds=chunk)
        available_modids.extend([file["modId"] for file in info])
    return list(set(available_modids))


# check curseforge_fingerprints queue
def check_curseforge_fingerprints_available():
    """
    返回对应的 modids
    """
    available_modids = []
    fingerprints = fetch_curseforge_fingerprints_queue()
    log.info(f"Fetched {len(fingerprints)} curseforge fingerprints from queue")

    for i in range(0, len(fingerprints), CURSEFORGE_LIMIT_SIZE):
        chunk = fingerprints[i : i + CURSEFORGE_LIMIT_SIZE]
        info = fetch_mutil_fingerprints(fingerprints=chunk)
        available_modids.extend(
            [fingerprint["file"]["modId"] for fingerprint in info["exactMatches"]]
        )
    return list(set(available_modids))


def check_new_modids(modids: List[int]) -> List[int]:
    """
    返回对应的 modids
    """
    find_result = raw_mongo_client["curseforge_mods"].find(
        {"_id": {"$in": modids}}, {"_id": 1}
    )
    found_modids = [mod["_id"] for mod in find_result]
    return list(set(modids) - set(found_modids))
