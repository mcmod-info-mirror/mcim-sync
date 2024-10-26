import os
from config.constants import CONFIG_PATH
from config.mcim import MCIMConfig
from config.mongodb import MongodbConfig

__all__ = [
    "MCIMConfig",
    "MongodbConfig",
]


if not os.path.exists(CONFIG_PATH):
    os.makedirs(CONFIG_PATH)
