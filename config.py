import json
import os
from typing import Optional
from pydantic import BaseModel, ValidationError, validator
from enum import Enum

# MCIM config path
MICM_CONFIG_PATH = os.path.join("config.json")

class MongodbConfigModel(BaseModel):
    host: str = "mongodb"
    port: int = 27017
    auth: bool = True
    user: str = "username"
    password: str = "password"
    database: str = "database"

class MCIMConfigModel(BaseModel):
    debug: bool = False
    mongodb: MongodbConfigModel = MongodbConfigModel()

    interval: int = 60 * 60 * 2 # 2 hours
    max_workers: int = 8
    sync_curseforge: bool = True
    sync_modrinth: bool = True

    curseforge_chunk_size: int = 1000
    modrinth_chunk_size: int = 1000

    curseforge_api_key: str = "<api key>"
    curseforge_api: str = "https://api.curseforge.com"  # 不然和api的拼接对不上
    modrinth_api: str = "https://api.modrinth.com/v2"
    proxies: Optional[str] = None

    file_cdn: bool = False
    max_file_size: int = 1024 * 1024 * 20

    log_to_file: bool = False
    log_path: str = "./logs"



class MCIMConfig:
    @staticmethod
    def save(model: MCIMConfigModel = MCIMConfigModel(), target=MICM_CONFIG_PATH):
        with open(target, "w") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=MICM_CONFIG_PATH) -> MCIMConfigModel:
        if not os.path.exists(target):
            MCIMConfig.save(target=target)
            return MCIMConfigModel()
        with open(target, "r") as fd:
            data = json.load(fd)
        return MCIMConfigModel(**data)
