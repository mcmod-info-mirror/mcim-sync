from typing import Union, List, Set
import datetime
import time

from mcim_sync.database.mongodb import raw_mongo_client
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.curseforge import Mod
from mcim_sync.sync.curseforge import (
    fetch_mutil_mods_info,
    fetch_mutil_files,
    fetch_mutil_fingerprints,
    fetch_search_result,
    ModsSearchSortOrder,
    ModsSearchSortField,
)
from mcim_sync.queues.curseforge import (
    fetch_curseforge_modids_queue,
    fetch_curseforge_fileids_queue,
    fetch_curseforge_fingerprints_queue,
)
from mcim_sync.utils.model_submitter import ModelSubmitter

config = Config.load()

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size

MAX_WORKERS: int = config.max_workers

CURSEFORGE_DELAY: Union[float, int] = config.curseforge_delay

def check_curseforge_data_updated(mods: List[Mod]) -> Set[int]:
    mod_date = {mod.id: {"sync_date": mod.dateModified} for mod in mods}
    expired_modids: Set[int] = set()
    mods_info = fetch_mutil_mods_info(modIds=[mod.id for mod in mods])
    if mods_info is not None:
        with ModelSubmitter() as submitter:
            for mod in mods_info:
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
                    log.trace(f"Mod {modid} is not updated, pass!")
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
        if info is not None:
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
        if info is not None:
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
        if info is not None:
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



def check_newest_search_result(gameId: int, classId: int) -> List[int]:
    """
    遍历搜索返回值直到出现第一个已缓存的 modid，然后返回所有捕捉到的新 modid
    """
    new_modids = []
    index = 0
    page_size = 50

    while index + page_size <= 10000:
        res = fetch_search_result(
            gameId=gameId, classId=classId, index=index, pageSize=page_size,
            sortField=ModsSearchSortField.ReleasedDate,
            sortOrder=ModsSearchSortOrder.DESC,
        )
        
        if res["pagination"]["resultCount"] == 0:
            break

        temp_modids = [mod["id"] for mod in res["data"]]

        # 检查哪些 mod 已经在数据库中
        existing_mods = set(
            doc["_id"] for doc in raw_mongo_client["curseforge_mods"].find(
                {"_id": {"$in": temp_modids}}, 
                {"_id": 1}
            )
        )

        # 如果找到任何已存在的 mod，停止搜索
        if existing_mods:
            new_ids = [mid for mid in temp_modids if mid not in existing_mods]
            new_modids.extend(new_ids)
            log.debug(f"Found {len(new_ids)} new modids at index {index}")
            break

        # 如果所有 mod 都是新的，添加它们并继续搜索
        new_modids.extend(temp_modids)
        log.debug(f"Found {len(temp_modids)} new modids at index {index}")

        index += page_size

        time.sleep(CURSEFORGE_DELAY)

    return new_modids