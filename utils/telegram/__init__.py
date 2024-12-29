from typing import List, Dict, Union
from pydantic import BaseModel
import telegram
import tenacity
from datetime import datetime
from telegram.error import TelegramError
from httpx._exceptions import NetworkError
from abc import ABC, abstractmethod

from utils.network import request_sync
from utils import SyncMode
from config import Config
from utils.loger import log

bot: telegram.Bot
config = Config.load()


def init_bot():
    global bot
    bot = telegram.Bot(
        token=config.bot_token,
        base_url=config.bot_api,
        request=telegram.request.HTTPXRequest(
            proxy=config.telegram_proxy, connection_pool_size=64
        ),
    )
    return bot


@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
async def send_message(text: str):
    await bot.send_message(chat_id=config.chat_id, text=text)
    log.info(f"Message '{text}' sent to telegram.")


class Notification(ABC):
    @abstractmethod
    async def send_to_telegram(self):
        pass


class RefreshNotification(Notification):
    def __init__(self, sync_mode: SyncMode = SyncMode.MODIFY_DATE):
        self.modrinth_refreshed_count: int = 0
        self.curseforge_refreshed_count: int = 0
        self.sync_mode: SyncMode = sync_mode

    async def send_to_telegram(self):
        sync_message = (
            f"本次同步为{self.sync_mode.value}同步\n"
            f"CurseForge: {self.curseforge_refreshed_count} 个 Mod 的数据已更新\n"
            f"Modrinth: {self.modrinth_refreshed_count} 个 Mod 的数据已更新"
        )
        """
        https://mod.mcimirror.top/statistics
        {
            "curseforge": {
                "mod": 75613,
                "file": 1265312,
                "fingerprint": 1264259
            },
            "modrinth": {
                "project": 42832,
                "version": 415467,
                "file": 458877
            },
            "file_cdn": {
                "file": 924573
            }
        }
        """
        mcim_stats = request_sync("https://mod.mcimirror.top/statistics").json()
        """
        MCIM 已缓存：
        Curseforge 模组 75613 个，文件 1265312 个，指纹 1264259 个
        Modrinth 项目 42832 个，版本 415467 个，文件 458877 个
        CDN 文件 924573 个
        """
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
        final_message = f"{sync_message}\n\n{mcim_message}\n\n{files_message}"
        await send_message(final_message)


class ProjectDetail(BaseModel):
    id: Union[int, str]
    name: str
    version_count: int


class SyncNotification(Notification):
    def __init__(self, platform: str, projects_detail_info: List[ProjectDetail]):
        self.platform: str = platform
        self.catched_count: int = len(projects_detail_info)
        self.projects_detail_info: List[ProjectDetail] = projects_detail_info

    async def send_to_telegram(self):
        message = f"本次从 API 请求中总共捕捉到 {self.catched_count} 个 {self.platform} 模组数据："
        for project in self.projects_detail_info:
            message += f"\n{project.name} (ID: {project.id}) 共有 {project.version_count} 个版本"

        await send_message(message)
