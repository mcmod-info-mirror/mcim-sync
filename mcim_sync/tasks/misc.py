from mcim_sync.utils.loger import log
from mcim_sync.utils.telegram import StatisticsNotification
from mcim_sync.config import Config

config = Config.load()


def send_statistics_to_telegram() -> bool:
    log.info("Start fetching statistics to telegram.")
    message = StatisticsNotification.send_to_telegram()
    log.info("Statistics message sent to telegram.")
    # log.info(f"Statistics message: {message}")
    return True
