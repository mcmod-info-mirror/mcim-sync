from typing import List, Dict, Union, Optional
from pydantic import BaseModel
import tenacity
from abc import ABC, abstractmethod
from telegram.helpers import escape_markdown


from mcim_sync.utils.network import request
from mcim_sync.models import ProjectDetail
from mcim_sync.config import Config
from mcim_sync.utils.loger import log

config = Config.load()


@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
def send_message_sync(
    text: str,
    chat_id: str,
    parse_mode: Optional[str] = None,
) -> int:
    data = {
        "chat_id": chat_id,
        "text": text,
        # TODO: 支持 Markdown
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    result = request(
        f"{config.bot_api}{config.bot_token}/sendMessage",
        method="POST",
        json=data,
        ignore_status_code=True,
    ).json()
    if result["ok"]:
        log.info(
            f"Message '{text}' sent to telegram, message_id: {result['result']['message_id']}"
        )
        return result["result"]["message_id"]
    else:
        raise Exception(
            f"Telegram API error: {result}, original message: {repr(text)}, parse_mode: {parse_mode}"
        )


@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
def pin_message(message_id: int, chat_id: str) -> bool:
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    result = request(
        f"{config.bot_api}{config.bot_token}/pinChatMessage",
        method="POST",
        json=data,
        ignore_status_code=True,
    ).json()
    if result["ok"]:
        log.info(f"Message {message_id} pinned to telegram")
        return True
    else:
        log.error(f"Telegram API error: {result}")
        raise Exception(
            f"Telegram API error: {result}, original message_id: {message_id}"
        )


class Notification(ABC):
    @abstractmethod
    def send_to_telegram(self):
        raise NotImplementedError()


def make_blockquote(lines: List[str], prefix: str = "> ") -> str:
    return (
        "**"
        + "\n".join([f"{prefix}{escape_markdown(line, version=2)}" for line in lines])
        + "||"
    )


def make_project_detail_blockquote(projects_detail_info: List[ProjectDetail]) -> str:
    """
    制作模组信息的折叠代码块
    """
    message = escape_markdown(f"\n以下格式为 模组名(模组ID): 版本数量\n", version=2)
    mod_messages = []
    message_length = len(message)
    for project in projects_detail_info:
        if message_length >= 3600:  # 不算代码块标识符的长度
            break
        text = f"{project.name}({project.id}): {project.version_count}"
        mod_messages.append(text)
        message_length += len(text)
    message += make_blockquote(mod_messages)
    return message


class StatisticsNotification(Notification):
    @classmethod
    def send_to_telegram(cls) -> int:
        mcim_stats = request("https://mod.mcimirror.top/statistics").json()
        files_stats = request("https://files.mcimirror.top/api/stats/center").json()
        mcim_message = (
            "MCIM API 已缓存：\n"
            f"Curseforge 模组 {mcim_stats['curseforge']['mod']} 个，文件 {mcim_stats['curseforge']['file']} 个，指纹 {mcim_stats['curseforge']['fingerprint']} 个\n"
            f"Modrinth 项目 {mcim_stats['modrinth']['project']} 个，版本 {mcim_stats['modrinth']['version']} 个，文件 {mcim_stats['modrinth']['file']} 个\n"
            f"CDN 文件 {mcim_stats['file_cdn']['file']} 个"
        )
        files_stats = request("https://files.mcimirror.top/api/stats/center").json()
        files_message = (
            f"OpenMCIM 数据统计：\n"
            f"当前在线节点：{files_stats['onlines']} 个\n"
            f"当日全网总请求：{files_stats['today']['hits']} 次\n"
            f"当日全网总流量：{files_stats['today']['bytes'] / 1024 / 1024 / 1024:.2f} GB\n"
            f"同步源数量：{files_stats['sources']} 个\n"
            f"总文件数：{files_stats['totalFiles']} 个\n"
            f"总文件大小：{files_stats['totalSize'] / 1024 / 1024 / 1024/ 1024:.2f} TB\n"
            f"#Statistics"
        )
        final_message = f"{mcim_message}\n\n{files_message}"
        message_id = send_message_sync(final_message, chat_id=config.chat_id)
        pin_message(message_id, chat_id=config.chat_id)
        return message_id


class RefreshNotification(Notification):
    platform: str
    projects_detail_info: List[ProjectDetail]

    def __init__(self, platform: str, projects_detail_info: List[ProjectDetail]):
        self.platform = platform
        self.projects_detail_info = projects_detail_info

    def send_to_telegram(self) -> int:
        sync_message = escape_markdown(
            f"{self.platform} 缓存刷新完成，共刷新 {len(self.projects_detail_info)} 个模组",
            version=2,
        )
        # if self.projects_detail_info:
        #     sync_message += escape_markdown(
        #         f"\n以下格式为 模组名(模组ID): 版本数量\n", version=2
        #     )
        #     mod_messages = []
        #     for project in self.projects_detail_info:
        #         mod_messages.append(
        #             f"{project.name}({project.id}): {project.version_count}"
        #         )
        #     sync_message += make_blockquote(mod_messages)
        if self.projects_detail_info:
            sync_message += make_project_detail_blockquote(self.projects_detail_info)
        sync_message += (
            "\n#Curseforge_Refresh"
            if self.platform == "Curseforge"
            else "\n#Modrinth_Refresh"
        )
        message_id = send_message_sync(
            sync_message, chat_id=config.chat_id, parse_mode="MarkdownV2"
        )
        return message_id


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

    def send_to_telegram(self) -> int:
        message = escape_markdown(
            (
                f"本次从 API 请求中总共捕捉到 {self.total_catached_count} 个 {self.platform} 的模组数据\n"
                f"有 {len(self.projects_detail_info)} 个模组是新捕获到的"
                f"#Curseforge_Sync"
                if self.platform == "Curseforge"
                else "#Modrinth_Sync"
            ),
            version=2,
        )

        if self.projects_detail_info:
            # mod_messages = []
            # message += escape_markdown(
            #     f"\n以下格式为 模组名(模组ID): 版本数量\n", version=2
            # )  # tmd 转义
            # for project in self.projects_detail_info:
            #     if len(message) > 4000:  # Telegram 限制消息长度 4096 字符
            #         break
            #     mod_messages.append(
            #         f"{project.name}({project.id}): {project.version_count}"
            #     )

            # message += make_blockquote(mod_messages)
            message += make_project_detail_blockquote(self.projects_detail_info)

        message_id = send_message_sync(
            message, parse_mode="MarkdownV2", chat_id=config.chat_id
        )
        return message_id


class CategoriesNotification(Notification):
    total_catached_count: int

    def __init__(self, total_catached_count: int):
        self.total_catached_count = total_catached_count

    def send_to_telegram(self) -> int:
        message = (
            f"已缓存 Curseforge Categories，共 {self.total_catached_count} 个分类\n"
            "#Curseforge_Categories"
        )
        message_id = send_message_sync(text=message, chat_id=config.chat_id)
        return message_id


class TagsNotification(Notification):
    categories_catached_count: int
    loeaders_cached_count: int
    game_versions_cached_count: int

    def __init__(
        self,
        categories_catached_count: int,
        loaders_cached_count: int,
        game_versions_cached_count: int,
    ):
        self.categories_catached_count = categories_catached_count
        self.loeaders_cached_count = loaders_cached_count
        self.game_versions_cached_count = game_versions_cached_count

    def send_to_telegram(self) -> int:
        message = (
            f"已缓存 Modrinth Tags\n"
            f"Categories 共 {self.categories_catached_count} 条\n"
            f"Loaders 共 {self.loeaders_cached_count} 条\n"
            f"Game_version 共 {self.game_versions_cached_count} 条\n"
            "#Modrinth_Tags"
        )
        message_id = send_message_sync(text=message, chat_id=config.chat_id)
        return message_id
