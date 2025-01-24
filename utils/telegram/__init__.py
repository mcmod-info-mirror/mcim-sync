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
def send_message_sync(text: str, parse_mode: str = None) -> int:
    data = {
        "chat_id": config.chat_id,
        "text": text,
        # TODO: 支持 Markdown
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    result = request_sync(
        f"{config.bot_api}{config.bot_token}/sendMessage",
        method="POST",
        json=data,
    ).json()
    if result["ok"]:
        log.info(f"Message '{text}' sent to telegram, message_id: {result['result']['message_id']}")
        return data["result"]['message_id']
    else:
        raise Exception(f"Telegram API error: {result}")

@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
def pin_message(message_id: int):
    data = {
        "chat_id": config.chat_id,
        "message_id": message_id,
    }
    result = request_sync(
        f"{config.bot_api}{config.bot_token}/pinChatMessage",
        method="POST",
        json=data,
    ).json()
    if result["ok"]:
        log.info(f"Message {message_id} pinned to telegram")
        return True
    else:
        log.error(f"Telegram API error: {result}")
        raise Exception(f"Telegram API error: {result}")


class Notification(ABC):
    @abstractmethod
    def send_to_telegram(self):
        pass


def make_blockquote(lines: List[str], prefix: str = ">") -> str:
    return "\n".join([f"{prefix}{line}" for line in lines])


def make_expandable_blockquote(lines: List[str], visible_lines: int = 5):
    if len(lines) >= visible_lines:
        # 前 visible_lines 行开头是 > 的引用块
        # visible_lines + 1 是 **>
        # 后续是 >
        # 最后一行是 >text||
        return (
            make_blockquote(lines[:visible_lines])
            + make_blockquote(lines[visible_lines : visible_lines + 1], prefix="**>")
            + make_blockquote(lines[visible_lines + 1 :], prefix=">")
            + make_blockquote(lines[visible_lines + 1 :])
            + "||"
        )
    else:
        make_blockquote(lines)


class StatisticsNotification(Notification):
    @classmethod
    def send_to_telegram(self):
        mcim_stats = request_sync("https://mod.mcimirror.top/statistics").json()
        files_stats = request_sync(
            "https://files.mcimirror.top/api/stats/center"
        ).json()
        mcim_message = (
            "MCIM API 已缓存：\n"
            f"Curseforge 模组 {mcim_stats['curseforge']['mod']} 个，文件 {mcim_stats['curseforge']['file']} 个，指纹 {mcim_stats['curseforge']['fingerprint']} 个\n"
            f"Modrinth 项目 {mcim_stats['modrinth']['project']} 个，版本 {mcim_stats['modrinth']['version']} 个，文件 {mcim_stats['modrinth']['file']} 个\n"
            f"CDN 文件 {mcim_stats['file_cdn']['file']} 个"
        )
        files_stats = request_sync(
            "https://files.mcimirror.top/api/stats/center"
        ).json()
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
        message_id = send_message_sync(final_message)
        pin_message(message_id)
        return final_message


class CurseforgeRefreshNotification(Notification):
    refreshed_count: int

    def __init__(self, refreshed_count: int):
        self.refreshed_count = refreshed_count

    def send_to_telegram(self):
        sync_message = f"Curseforge 缓存刷新完成，共刷新 {self.refreshed_count} 个模组"
        send_message_sync(sync_message)


class ModrinthRefreshNotification(Notification):
    refreshed_count: int

    def __init__(self, refreshed_count: int):
        self.refreshed_count = refreshed_count

    def send_to_telegram(self):
        sync_message = f"Modrinth 缓存刷新完成，共刷新 {self.refreshed_count} 个模组"
        send_message_sync(sync_message)


class ProjectDetail(BaseModel):
    id: Union[int, str]
    name: str
    version_count: int


class SyncNotification(Notification):
    platform: str
    total_catached_count: int
    projects_detail_info: List[ProjectDetail]

    def __init__(
        self,
        platform: str,
        total_catached_count: int,
        projects_detail_info: List[ProjectDetail],
    ):
        self.platform = platform
        self.total_catached_count = total_catached_count
        self.projects_detail_info = projects_detail_info

    def send_to_telegram(self):
        message = (
            f"本次从 API 请求中总共捕捉到 {self.total_catached_count} 个 {self.platform} 的模组数据\n"
            + f"有 {len(self.projects_detail_info)} 个模组是新捕获到的"
        )
        mod_messages = []
        if self.projects_detail_info:
            message += f"\n以下格式为 模组名(模组ID): 版本数量\n"
            for project in self.projects_detail_info:
                if len(message) > 4000:  # Telegram 限制消息长度 4096 字符
                    break
                mod_messages.append(
                    f"{project.name}({project.id}): {project.version_count}"
                )

            message += make_expandable_blockquote(mod_messages)

        message_id = send_message_sync(message, parse_mode="MarkdownV2")