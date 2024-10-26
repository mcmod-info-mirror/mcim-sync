import json
import os
from typing import Optional
from pydantic import BaseModel, ValidationError, validator
from enum import Enum

from .constants import CONFIG_PATH

# MCIM config path
MICM_CONFIG_PATH = os.path.join(CONFIG_PATH, "mcim.json")


class Curseforge(BaseModel):
    mod: int = 86400
    file: int = 86400
    fingerprint: int = 86400 * 7  # 一般不刷新
    search: int = 7200
    categories: int = 86400 * 7


class Modrinth(BaseModel):
    project: int = 86400
    version: int = 86400
    file: int = 86400 * 7  # 一般不刷新
    search: int = 7200
    category: int = 86400 * 7


class ExpireSecond(BaseModel):
    curseforge: Curseforge = Curseforge()
    modrinth: Modrinth = Modrinth()

class FileCDNRedirectMode(str, Enum):
    # 重定向到alist
    ALIST = "alist"
    # 重定向到原始链接
    ORIGIN = "origin"
    # 重定向到 open93home
    OPEN93HOME = "open93home"


class MCIMConfigModel(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    curseforge_api_key: str = "<api key>"
    curseforge_api: str = "https://api.curseforge.com"  # 不然和api的拼接对不上
    modrinth_api: str = "https://api.modrinth.com/v2"
    proxies: Optional[str] = None

    file_cdn: bool = False
    file_cdn_redirect_mode: FileCDNRedirectMode = FileCDNRedirectMode.ALIST
    file_cdn_secret: str = "secret"
    max_file_size: int = 1024 * 1024 * 20
    aria2: bool = False
    modrinth_download_path: str = "/modrinth"
    curseforge_download_path: str = "/curseforge"

    prometheus: bool = False

    redis_cache: bool = True
    alist_endpoint: str = "http://127.0.0.1:5244"
    open93home_endpoint: str = "http://open93home"

    expire_second: ExpireSecond = ExpireSecond()
    expire_status_code: int = 404
    uncache_status_code: int = 404

    log_to_file: bool = False
    log_path: str = "./logs"

    favicon_url: str = (
        "https://thirdqq.qlogo.cn/g?b=sdk&k=ABmaVOlfKKPceB5qfiajxqg&s=640"
    )


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
