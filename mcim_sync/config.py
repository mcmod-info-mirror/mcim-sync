import json
import os
from typing import Optional, Union, Dict
from pydantic import BaseModel, field_validator

# config path
CONFIG_PATH = os.path.join("config.json")


class MongodbConfigModel(BaseModel):
    host: str = "localhost"
    port: int = 27017
    auth: bool = False
    user: Optional[str] = None
    password: Optional[str] = None
    database: str = "database"


class RedisConfigModel(BaseModel):
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    database: int = 0

class JobConfigModel(BaseModel):
    curseforge_refresh: bool = True
    curseforge_refresh_full: bool = True
    modrinth_refresh: bool = True
    sync_curseforge_by_queue: bool = True
    sync_curseforge_by_search: bool = True
    sync_modrinth_by_queue: bool = True
    sync_modrinth_by_search: bool = True
    curseforge_categories: bool = True
    modrinth_tags: bool = True
    global_statistics: bool = True

    @field_validator('*', mode='before')
    def validate_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ('true', '1')
        return bool(v)


class JobInterval(BaseModel):
    curseforge_refresh: int = 60 * 60 * 2  # 2 hours
    modrinth_refresh: int = 60 * 60 * 2  # 2 hours
    curseforge_refresh_full: int = 60 * 60 * 48  # 48 hours
    sync_curseforge_by_queue: int = 60 * 5  # 5 minutes
    sync_curseforge_by_search: int = 60 * 60 * 2 # 2 hours
    sync_modrinth_by_queue: int = 60 * 5  # 5 minutes
    sync_modrinth_by_search: int = 60 * 60 * 2  # 2 hours
    curseforge_categories: int = 60 * 60 * 24  # 24 hours
    modrinth_tags: int = 60 * 60 * 24  # 24 hours
    global_statistics: int = 60 * 60 * 24  # 24 hours


class DomainRateLimitModel(BaseModel):
    """域名限速配置"""
    max_requests: int = 10  # 最大请求数
    time_window: int = 60   # 时间窗口（秒）


class ConfigModel(BaseModel):
    debug: bool = False
    mongodb: MongodbConfigModel = MongodbConfigModel()
    redis: RedisConfigModel = RedisConfigModel()
    job_config: JobConfigModel = JobConfigModel()
    interval: JobInterval = JobInterval()
    max_workers: int = 8
    curseforge_chunk_size: int = 1000
    modrinth_chunk_size: int = 100
    curseforge_delay: Union[float, int] = 1
    modrinth_delay: Union[float, int] = 1
    curseforge_api_key: str = "<api key>"
    curseforge_api: str = "https://api.curseforge.com"  # 不然和api的拼接对不上
    modrinth_api: str = "https://api.modrinth.com"
    telegram_bot: bool = False
    bot_api: str = "https://api.telegram.org/bot"
    bot_token: str = "<bot token>"
    chat_id: str = "<chat id>"
    telegram_proxy: Optional[str] = None
    proxies: Optional[str] = None
    file_cdn: bool = False
    max_file_size: int = 1024 * 1024 * 20  # 20MB
    log_to_file: bool = False
    log_path: str = "./logs"
    # 域名限速配置
    domain_rate_limits: Dict[str, DomainRateLimitModel] = {
        "api.curseforge.com": DomainRateLimitModel(max_requests=100, time_window=60),
        "api.modrinth.com": DomainRateLimitModel(max_requests=300, time_window=60),
    }


class Config:
    @staticmethod
    def save(model: ConfigModel = ConfigModel(), target=CONFIG_PATH):
        with open(target, "w") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=CONFIG_PATH) -> ConfigModel:
        if not os.path.exists(target):
            Config.save(target=target)
            return ConfigModel()
        with open(target, "r") as fd:
            data = json.load(fd)
        return ConfigModel(**data)
