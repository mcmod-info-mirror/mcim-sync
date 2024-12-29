from redis import Redis

from config import Config

_redis_config = Config.load().redis


def init_redis_syncengine() -> Redis:
    global sync_redis_engine
    sync_redis_engine = Redis(
        host=_redis_config.host,
        port=_redis_config.port,
        password=_redis_config.password,
        db=_redis_config.database,
    )
    return sync_redis_engine


def close_redis():
    sync_redis_engine.close()


sync_redis_engine: Redis = init_redis_syncengine()
