from odmantic import AIOEngine, SyncEngine
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from config import Config
from models.database.curseforge import Mod, File, Fingerprint
from models.database.modrinth import Project, Version, File as ModrinthFile
from models.database.file_cdn import File as CDNFile

_mongodb_config = Config.load().mongodb


def init_mongodb_syncengine() -> SyncEngine:
    """
    Raw Motor client handler, use it when beanie cannot work
    :return:
    """
    global sync_mongo_engine
    sync_mongo_engine = SyncEngine(
        client=MongoClient(
            f"mongodb://{_mongodb_config.user}:{_mongodb_config.password}@{_mongodb_config.host}:{_mongodb_config.port}"
            if _mongodb_config.auth
            else f"mongodb://{_mongodb_config.host}:{_mongodb_config.port}"
        ),
        database="mcim_backend",
    )
    return sync_mongo_engine


sync_mongo_engine: SyncEngine = init_mongodb_syncengine()
