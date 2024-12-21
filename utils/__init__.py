from typing import Union, List, Set
from enum import Enum

from models.database.curseforge import Mod
from models.database.modrinth import Project
from database.mongodb import sync_mongo_engine
from utils.loger import log

class SyncMode(Enum):
    MODIFY_DATE = "增量"
    FULL = "全量"

def submit_models(models: List[Union[Mod, Project]]):
    """
    提交到数据库

    应该尽量多次提交，少缓存在内存中
    """
    if len(models) != 0:
        sync_mongo_engine.save_all(models)
        log.debug(f"Submited models: {len(models)}")

