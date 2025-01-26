import json
import os
from typing import Optional, Union
from pydantic import BaseModel, ValidationError, validator
from enum import Enum

# config path
MICM_CONFIG_PATH = os.path.join("config.json")

class MongodbConfigModel(BaseModel):
    host: str = "mongodb"
    port: int = 27017
    auth: bool = True
    user: Optional[str] = None
    password: Optional[str] = None
    database: str = "database"

class RedisConfigModel(BaseModel):
    host: str = "redis"
    port: int = 6379
    password: Optional[str] = None
    database: int = 0

class JobInterval(BaseModel):
    curseforge_refresh: int = 60 * 60 * 2 # 2 hours
    modrinth_refresh: int = 60 * 60 * 2 # 2 hours
    sync_curseforge: int = 60 * 5 # 5 minutes
    sync_modrinth: int = 60 * 5 # 5 minutes
    curseforge_categories: int = 60 * 60 * 24 # 24 hours
    global_statistics: int = 60 * 60 * 24 # 24 hours

class ConfigModel(BaseModel):
    debug: bool = False
    mongodb: MongodbConfigModel = MongodbConfigModel()
    redis: RedisConfigModel = RedisConfigModel()
    interval: JobInterval = JobInterval()
    max_workers: int = 8
    sync_curseforge: bool = True
    sync_modrinth: bool = True
    curseforge_chunk_size: int = 1000
    modrinth_chunk_size: int = 1000
    curseforge_delay: Union[float, int] = 1
    modrinth_delay: Union[float, int] = 1
    curseforge_api_key: str = "<api key>"
    curseforge_api: str = "https://api.curseforge.com"  # 不然和api的拼接对不上
    modrinth_api: str = "https://api.modrinth.com/v2"
    telegram_bot: bool = False
    bot_api: str = "https://api.telegram.org/bot"
    bot_token: str = "<bot token>"
    chat_id: str = "<chat id>"
    telegram_proxy: Optional[str] = None
    proxies: Optional[str] = None
    file_cdn: bool = False
    max_file_size: int = 1024 * 1024 * 20 # 20MB
    log_to_file: bool = False
    log_path: str = "./logs"



class Config:
    @staticmethod
    def save(model: ConfigModel = ConfigModel(), target=MICM_CONFIG_PATH):
        with open(target, "w") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=MICM_CONFIG_PATH) -> ConfigModel:
        if not os.path.exists(target):
            Config.save(target=target)
            return ConfigModel()
        with open(target, "r") as fd:
            data = json.load(fd)
        return ConfigModel(**data)
