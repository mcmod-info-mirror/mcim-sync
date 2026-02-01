from odmantic import SyncEngine
from pymongo import MongoClient
from pymongo.database import Database
from pymongo import errors as pymongo_errors
from mcim_sync.config import Config

_mongodb_config = Config.load().mongodb

def ping_mongodb_client(client: MongoClient) -> bool:
    try:
        client.admin.command('ping')
        print("Successfully connected to MongoDB")
        return True
    except Exception as e:
        print(f"An error occurred: {e}, failed to connect to MongoDB")
        return False

def init_mongodb_syncengine() -> SyncEngine:
    """
    Raw Motor client handler, use it when beanie cannot work
    :return:
    """
    global sync_mongo_engine

    client = MongoClient(
            f"mongodb://{_mongodb_config.user}:{_mongodb_config.password}@{_mongodb_config.host}:{_mongodb_config.port}"
            if _mongodb_config.auth
            else f"mongodb://{_mongodb_config.host}:{_mongodb_config.port}"
        )
    ping_result = ping_mongodb_client(client)
    if not ping_result:
        client.close()
        exit(1)

    sync_mongo_engine = SyncEngine(
        client=client,
        database=_mongodb_config.database,
    )
    return sync_mongo_engine


def init_mongodb_raw_client() -> Database:
    global raw_mongo_client
    raw_mongo_client = MongoClient(
        f"mongodb://{_mongodb_config.user}:{_mongodb_config.password}@{_mongodb_config.host}:{_mongodb_config.port}"
        if _mongodb_config.auth
        else f"mongodb://{_mongodb_config.host}:{_mongodb_config.port}"
    )
    ping_result = ping_mongodb_client(raw_mongo_client)
    if not ping_result:
        raw_mongo_client.close()
        exit(1)
    return raw_mongo_client[_mongodb_config.database]


sync_mongo_engine: SyncEngine = init_mongodb_syncengine()
raw_mongo_client: Database = init_mongodb_raw_client()
