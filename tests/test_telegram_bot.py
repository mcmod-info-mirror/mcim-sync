import os

from utils.telegram import send_message_sync, pin_message, StatisticsNotification
from config import Config

config = Config.load()

chat_id = os.getenv("CHAT_ID")
if chat_id is None:
    raise ValueError("CHAT_ID is not set")

config.telegram_bot = True
config.chat_id = chat_id

pin_message_id: int = 0


def test_send_message_sync():
    message_id = send_message_sync("Hello, World!", chat_id=chat_id)  # test PlainText
    assert isinstance(message_id, int)
    message_id = send_message_sync(
        "Hello, World!", parse_mode="MarkdownV2", chat_id=chat_id
    )  # test MarkdownV2
    assert isinstance(message_id, int)
    global pin_message_id
    pin_message_id = message_id


def test_pin_message():
    global pin_message_id
    if pin_message_id == 0:
        raise ValueError("pin_message_id is not set")
    result = pin_message(pin_message_id, chat_id=chat_id)
    assert result == True


def test_send_message_static():
    assert StatisticsNotification.send_to_telegram()