import pytest
from telegram.helpers import escape_markdown

from mcim_sync.utils.telegram import send_message_sync, pin_message, StatisticsNotification
from mcim_sync.config import Config

config = Config.load()

pin_message_id: int = 0

skip_mark = pytest.mark.skipif(
    not config.telegram_bot, reason="config.telegram_bot is False, skip tests"
)

@skip_mark
def test_send_message_sync():
    message_id = send_message_sync("Hello, World!", chat_id=config.chat_id)  # test PlainText
    assert isinstance(message_id, int)
    message_id = send_message_sync(
        escape_markdown("Hello, World!", version=2), parse_mode="MarkdownV2", chat_id=config.chat_id
    )  # test MarkdownV2
    global pin_message_id
    pin_message_id = message_id
    assert isinstance(message_id, int)


@skip_mark
def test_pin_message():
    if pin_message_id == 0:
        raise ValueError("pin_message_id is not set")
    result = pin_message(pin_message_id, chat_id=config.chat_id)
    assert result == True


@skip_mark
def test_send_message_static():
    assert isinstance(StatisticsNotification.send_to_telegram(), int)
