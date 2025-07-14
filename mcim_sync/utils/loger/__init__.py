from loguru import logger
import os
import sys
import logging
import time

from mcim_sync.config import Config

if os.getenv("TZ") is not None:
    time.tzset()

config = Config.load()

EXCLUDED_KEYWORDS = ["httpx"]


LOGGING_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "  # 时间
    "{process.name} | "  # 进程名
    "{thread.name} | "  # 线程名
    "<cyan>{module}</cyan>.<cyan>{function}</cyan> | "  # 模块名.方法名
    "<cyan>{line}</cyan> | "  # 行号
    "<level>{level}</level>: "  # 等级
    "<level>{message}</level>"  # 日志内容
)


def filter(record) -> bool:
    """
    Filter out log entries for excluded endpoints.

    Args:
        record: The log record to be filtered.

    Returns:
        bool: True if the log entry should be included, False otherwise.
    """
    if isinstance(record, logging.LogRecord):
        return record.args and len(record.args) >= 3
    return not any(keyword in record["message"] for keyword in EXCLUDED_KEYWORDS)


class Logger:
    """输出日志到文件和控制台"""

    def __init__(self):
        # 文件的命名
        self.logger = logger
        # 清空所有设置
        self.logger.remove()
        # 添加控制台输出的配置
        self.logger.add(
            sys.stdout,
            format=LOGGING_FORMAT,
            level="INFO" if not config.debug else "DEBUG",
            backtrace=False,
            diagnose=False,
            filter=filter,
            serialize=True,
        )

    def get_logger(self):
        return self.logger


Loggers = Logger()
log = Loggers.get_logger()
