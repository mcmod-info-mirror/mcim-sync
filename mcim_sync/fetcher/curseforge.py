from typing import Union, List
import time

from mcim_sync.database.mongodb import sync_mongo_engine
from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.models.database.curseforge import Mod
from mcim_sync.checker.curseforge import check_curseforge_data_updated

config = Config.load()

CURSEFORGE_LIMIT_SIZE: int = config.curseforge_chunk_size
MODRINTH_LIMIT_SIZE: int = config.modrinth_chunk_size
MAX_WORKERS: int = config.max_workers
CURSEFORGE_DELAY: Union[float, int] = config.curseforge_delay
MODRINTH_DELAY: Union[float, int] = config.modrinth_delay



def fetch_all_curseforge_data() -> List[int]:
    skip = 0
    result = []
    while True:
        mods_result: List[Mod] = list(
            sync_mongo_engine.find(Mod, skip=skip, limit=CURSEFORGE_LIMIT_SIZE)
        )

        if not mods_result:
            break
        skip += CURSEFORGE_LIMIT_SIZE
        result.extend([mod.id for mod in mods_result])
        # time.sleep(CURSEFORGE_DELAY)
        # log.debug(f"Delay {CURSEFORGE_DELAY} seconds")
    return result


def fetch_expired_curseforge_data() -> List[int]:
    expired_modids = set()
    skip = 0
    while True:
        mods_result: List[Mod] = list(
            sync_mongo_engine.find(Mod, skip=skip, limit=CURSEFORGE_LIMIT_SIZE)
        )

        if not mods_result:
            break
        skip += CURSEFORGE_LIMIT_SIZE
        check_expired_result = check_curseforge_data_updated(mods_result)
        expired_modids.update(check_expired_result)
        log.debug(f"Matched {len(check_expired_result)} expired mods")
        time.sleep(CURSEFORGE_DELAY)
        log.debug(f"Delay {CURSEFORGE_DELAY} seconds")
    return list(expired_modids)
