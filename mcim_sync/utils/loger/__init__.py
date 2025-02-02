from loguru import logger
import os
import sys
import logging
import time

from mcim_sync.config import Config

if os.getenv("TZ") is not None:
    time.tzset()

config = Config.load()

LOG_PATH = config.log_path
if config.log_to_file:
    os.makedirs(LOG_PATH, exist_ok=True)

EXCLUDED_KEYWORDS = ["httpx"]


LOGGING_FORMAT = "<green>{time:YYYYMMDD HH:mm:ss}</green> | "  # 颜色>时间
"{process.name} | "  # 进程名
"{thread.name} | "  # 进程名
"<cyan>{module}</cyan>.<cyan>{function}</cyan> | "  # 模块名.方法名
":<cyan>{line}</cyan> | "  # 行号
"<level>{level}</level>: "  # 等级
"<level>{message}</level>"  # 日志内容


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
        log_path = os.path.join(LOG_PATH, "{time:YYYY-MM-DD}.log")
        self.logger = logger
        # 清空所有设置
        self.logger.remove()
        # 判断日志文件夹是否存在，不存则创建
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
        # 添加控制台输出的格式,sys.stdout为输出到屏幕;关于这些配置还需要自定义请移步官网查看相关参数说明
        self.logger.add(
            sys.stdout,
            format=LOGGING_FORMAT,
            level="INFO" if not config.debug else "DEBUG",
            backtrace=False,
            diagnose=False,
            filter=filter,
            serialize=True,
        )
        if config.log_to_file:
            # 日志写入文件
            self.logger.add(
                log_path,  # 写入目录指定文件
                format=LOGGING_FORMAT,
                encoding="utf-8",
                retention="7 days",  # 设置历史保留时长
                backtrace=True,  # 回溯
                diagnose=True,  # 诊断
                enqueue=True,  # 异步写入
                rotation="00:00",  # 每日更新时间
                # rotation="5kb",  # 切割，设置文件大小，rotation="12:00"，rotation="1 week"
                # filter="my_module"  # 过滤模块
                # compression="zip"   # 文件压缩
                level="INFO" if not config.debug else "DEBUG",
                filter=filter,
            )

    def get_logger(self):
        return self.logger


Loggers = Logger()
log = Loggers.get_logger()
