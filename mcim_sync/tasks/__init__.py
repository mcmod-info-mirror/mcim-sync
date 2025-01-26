import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from mcim_sync.utils.loger import log
from mcim_sync.config import Config
from mcim_sync.exceptions import ResponseCodeException, TooManyRequestsException


config = Config.load()

# 429 全局暂停
curseforge_pause_event = threading.Event()
modrinth_pause_event = threading.Event()

def sync_with_pause(sync_function, *args):
    times = 0
    if "curseforge" in threading.current_thread().name:
        pause_event = curseforge_pause_event
        thread_type = "CurseForge"
    elif "modrinth" in threading.current_thread().name:
        pause_event = modrinth_pause_event
        thread_type = "Modrinth"
    else:
        log.error(
            f"Unknown thread name {threading.current_thread().name}, can't determine pause event."
        )
        return
    while times < 3:
        # 检查是否需要暂停
        pause_event.wait()
        try:
            return sync_function(*args)

        except (ResponseCodeException, TooManyRequestsException) as e:
            if e.status_code in [429, 403]:
                log.warning(
                    f"Received HTTP {e.status_code}, pausing all {thread_type} threads for 30 seconds..."
                )
                pause_event.clear()
                time.sleep(30)
                pause_event.set()
                log.info("Resuming all threads.")
        else:
            break
    else:
        log.error(
            f"Failed to sync data after 3 retries, func: {sync_function}, args: {args}"
        )


def create_tasks_pool(sync_function, data, max_workers, thread_name_prefix):
    thread_pool = ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix=thread_name_prefix
    )
    futures = [
        thread_pool.submit(sync_with_pause, sync_function, item) for item in data
    ]
    return thread_pool, futures
