from typing import List, Dict, Union, Sequence
from pydantic import BaseModel
import tenacity
from abc import ABC, abstractmethod

from utils.network import request_sync
from utils import SyncMode
from config import Config
from utils.loger import log

config = Config.load()


@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
def send_message_sync(text: str):
    request_sync(
        f"{config.bot_api}{config.bot_token}/sendMessage",
        method="POST",
        json={
            "chat_id": config.chat_id,
            "text": text,
            # TODO: 支持 Markdown
            # "parse_mode": "Markdown", 
        },
    )
    log.info(f"Message '{text}' sent to telegram.")

class Notification(ABC):
    @abstractmethod
    def send_to_telegram(self):
        pass

class StatisticsNotification(Notification):
    @classmethod
    def send_to_telegram(self):
        mcim_stats = request_sync("https://mod.mcimirror.top/statistics").json()
        files_stats = request_sync("https://files.mcimirror.top/api/stats/center").json()
        mcim_message = (
            "MCIM API 已缓存：\n"
            f"Curseforge 模组 {mcim_stats['curseforge']['mod']} 个，文件 {mcim_stats['curseforge']['file']} 个，指纹 {mcim_stats['curseforge']['fingerprint']} 个\n"
            f"Modrinth 项目 {mcim_stats['modrinth']['project']} 个，版本 {mcim_stats['modrinth']['version']} 个，文件 {mcim_stats['modrinth']['file']} 个\n"
            f"CDN 文件 {mcim_stats['file_cdn']['file']} 个"
        )
        """
        https://files.mcimirror.top/api/stats/center
        {
        "today": {
            "hits": 69546,
            "bytes": 112078832941
        },
        "onlines": 7,
        "sources": 1,
        "totalFiles": 922998,
        "totalSize": 1697281799794,
        "startTime": 1730551551412
        }
        """
        files_stats = request_sync(
            "https://files.mcimirror.top/api/stats/center"
        ).json()
        """
        当前在线节点：6 个
        当日全网总请求：67597 次
        当日全网总流量：100.89 GB
        同步源数量：1 个
        总文件数：922998 个
        总文件大小：1.54 TB
        主控在线时间：0 天 5 小时 12 分钟 14 秒
        请求时间：2024 年 11 月 03 日 01:58:05
        """
        files_message = (
            f"OpenMCIM 数据统计：\n"
            f"当前在线节点：{files_stats['onlines']} 个\n"
            f"当日全网总请求：{files_stats['today']['hits']} 次\n"
            f"当日全网总流量：{files_stats['today']['bytes'] / 1024 / 1024 / 1024:.2f} GB\n"
            f"同步源数量：{files_stats['sources']} 个\n"
            f"总文件数：{files_stats['totalFiles']} 个\n"
            f"总文件大小：{files_stats['totalSize'] / 1024 / 1024 / 1024/ 1024:.2f} TB\n"
        )
        final_message = f"{mcim_message}\n\n{files_message}"
        send_message_sync(final_message)
        return final_message

class CurseforgeRefreshNotification(Notification):
    def __init__(self, count: int):
        self.refreshed_count: int = count

    def send_to_telegram(self):
        sync_message = (
            f"Curseforge 缓存刷新完成，共刷新 {self.refreshed_count} 个模组"
        )
        send_message_sync(sync_message)

class ModrinthRefreshNotification(Notification):
    def __init__(self, count: int):
        self.refreshed_count: int = count

    def send_to_telegram(self):
        sync_message = (
            f"Modrinth 缓存刷新完成，共刷新 {self.refreshed_count} 个模组"
        )
        send_message_sync(sync_message)


class ProjectDetail(BaseModel):
    id: Union[int, str]
    name: str
    version_count: int


class SyncNotification(Notification):
    def __init__(self, platform: str, total_catached_count: int, projects_detail_info: List[ProjectDetail]):
        self.platform: str = platform
        self.total_catached_count: int = total_catached_count
        self.projects_detail_info: List[ProjectDetail] = projects_detail_info

    def send_to_telegram(self):
        message = f"本次从 API 请求中总共捕捉到 {self.total_catached_count} 个 {self.platform} 的模组数据" + \
                    f'有 {len(self.projects_detail_info)} 个模组是新捕获到的' + \
                    f'以下格式为 模组名(模组ID): 版本数量'
        for project in self.projects_detail_info:
            if len(message) > 4000: # Telegram 限制消息长度 4096 字符
                break
            message += f"\n{project.name}({project.id}): {project.version_count}"
            
        send_message_sync(message)