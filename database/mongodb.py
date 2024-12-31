from odmantic import AIOEngine, SyncEngine
from pymongo import MongoClient
from pymongo.database import Database

from config import Config

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
        database=_mongodb_config.database,
    )
    return sync_mongo_engine


def init_mongodb_raw_client() -> Database:
    global raw_mongo_client
    raw_mongo_client = MongoClient(
        f"mongodb://{_mongodb_config.user}:{_mongodb_config.password}@{_mongodb_config.host}:{_mongodb_config.port}"
        if _mongodb_config.auth
        else f"mongodb://{_mongodb_config.host}:{_mongodb_config.port}"
    )[_mongodb_config.database]
    return raw_mongo_client


sync_mongo_engine: SyncEngine = init_mongodb_syncengine()
raw_mongo_client: Database = init_mongodb_raw_client()
