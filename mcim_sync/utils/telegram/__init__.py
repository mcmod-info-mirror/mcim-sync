from typing import List, Optional
import tenacity
from abc import ABC, abstractmethod
from telegram.helpers import escape_markdown as _escape_markdown


from mcim_sync.utils.network import request
from mcim_sync.config import Config
from mcim_sync.utils.loger import log
from mcim_sync.utils.constants import Platform, ProjectDetail

config = Config.load()

TELEGRAM_MAX_CHARS = 4096  # Telegram 文本消息最大长度


def escape_markdown(text: str) -> str:
    return _escape_markdown(text=text, version=2)


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

def make_spoiler_block_with_budget(
    lines: List[str], budget: int, prefix: str = "> "
) -> str:
    budget -= 4  # 扣除 '**' '||' 的长度
    assembled_lines: List[str] = []
    used = 0
    for line in lines:
        # 逐行转义并加入前缀
        escaped_line = f"{prefix}{escape_markdown(line, version=2)}"
        # 如果不是第一行，需要额外的换行符
        increment = len(escaped_line) + (1 if assembled_lines else 0)
        if used + increment > budget:
            break
        assembled_lines.append(escaped_line)
        used += increment
    newline = "\n"
    return f"**{newline.join(assembled_lines)}||"


class StatisticsNotification(Notification):
    @classmethod
    def send_to_telegram(cls) -> int:
        mcim_stats = request("https://mod.mcimirror.top/statistics").json()
        mcim_message = (
            "MCIM API 已缓存：\n"
            f"Curseforge 模组 {mcim_stats['curseforge']['mod']} 个，文件 {mcim_stats['curseforge']['file']} 个\n"
            f"Modrinth 项目 {mcim_stats['modrinth']['project']} 个，版本 {mcim_stats['modrinth']['version']} 个，文件 {mcim_stats['modrinth']['file']} 个\n"
            f"Curseforge 已翻译 {mcim_stats['translate']['curseforge']} 个，Modrinth 已翻译 {mcim_stats['translate']['modrinth']} 个"
        )

        message_id = send_message_sync(mcim_message, chat_id=config.chat_id)
        pin_message(message_id, chat_id=config.chat_id)
        return message_id


class RefreshNotification(Notification):
    platform: Platform
    projects_detail_info: List[ProjectDetail]
    failed_count = 0  # 失败的模组数量

    def __init__(
        self,
        platform: Platform,
        projects_detail_info: List[ProjectDetail],
        failed_count: Optional[int] = 0,
    ):
        self.platform = platform
        self.projects_detail_info = projects_detail_info
        self.failed_count = failed_count if failed_count is not None else 0

    def send_to_telegram(self) -> int:
        sync_message = escape_markdown(
            f"{self.platform.value} 缓存刷新完成，共刷新 {len(self.projects_detail_info)} 个模组, {self.failed_count} 个模组刷新失败\n"
            if self.failed_count > 0
            else f"{self.platform.value} 缓存刷新完成，共刷新 {len(self.projects_detail_info)} 个模组\n"
        )
        tag_message = escape_markdown(
            text=(
                "\n#Curseforge_Refresh"
                if self.platform == Platform.CURSEFORGE
                else "\n#Modrinth_Refresh"
            )
        )
        if self.projects_detail_info:
            sync_message += escape_markdown("\n以下格式为 模组名(模组ID): 版本数量\n")
            sync_message += make_spoiler_block_with_budget(
                self.projects_detail_info,
                budget=TELEGRAM_MAX_CHARS - len(sync_message) - len(tag_message),
            )
        sync_message += tag_message
        message_id = send_message_sync(
            sync_message, chat_id=config.chat_id, parse_mode="MarkdownV2"
        )
        return message_id


class QueueSyncNotification(Notification):
    platform: Platform
    total_catached_count: int
    projects_detail_info: List[ProjectDetail]

    def __init__(
        self,
        platform: Platform,
        total_catached_count: int,
        projects_detail_info: List[ProjectDetail],
    ):
        self.platform = platform
        self.total_catached_count = total_catached_count
        self.projects_detail_info = projects_detail_info

    def send_to_telegram(self) -> int:
        message = escape_markdown(
            (
                f"本次从 API 请求中总共捕捉到 {self.total_catached_count} 个 {self.platform.value.capitalize()} 的模组数据\n"
                f"有 {len(self.projects_detail_info)} 个模组是新捕获到的"
            )
        )
        tag_message = escape_markdown(
            text=(
                "\n#Curseforge_Queue"
                if self.platform == Platform.CURSEFORGE
                else "\n#Modrinth_Queue"
            )
        )
        if self.projects_detail_info:
            message += escape_markdown("\n以下格式为 模组名(模组ID): 版本数量\n")
            message += make_spoiler_block_with_budget(
                self.projects_detail_info,
                budget=TELEGRAM_MAX_CHARS - len(message) - len(tag_message),
            )
        message += tag_message
        message_id = send_message_sync(
            message, parse_mode="MarkdownV2", chat_id=config.chat_id
        )
        return message_id


class SearchSyncNotification(Notification):
    platform: Platform
    total_catached_count: int
    projects_detail_info: List[ProjectDetail]

    def __init__(
        self,
        platform: Platform,
        total_catached_count: int,
        projects_detail_info: List[ProjectDetail],
    ):
        self.platform = platform
        self.total_catached_count = total_catached_count
        self.projects_detail_info = projects_detail_info

    def send_to_telegram(self) -> int:
        message = escape_markdown(
            (
                f"本次从 {self.platform.value} 搜索接口中总共找到 {self.total_catached_count} 个新项目数据\n"
            )
        )
        tag_message = escape_markdown(
            text=(
                "\n#Curseforge_Search"
                if self.platform == Platform.CURSEFORGE
                else "\n#Modrinth_Search"
            )
        )
        if self.projects_detail_info:
            message += escape_markdown("\n以下格式为 模组名(模组ID): 版本数量\n")
            message += make_spoiler_block_with_budget(self.projects_detail_info, budget=TELEGRAM_MAX_CHARS - len(message) - len(tag_message))
        message += tag_message
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
