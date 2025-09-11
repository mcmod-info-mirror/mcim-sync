from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

@contextmanager
def create_tasks_pool(sync_function, data, max_workers, thread_name_prefix):
    # 创建线程池
    thread_pool = ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix=thread_name_prefix
    )
    
    try:
        # 提交所有任务
        futures = [
            thread_pool.submit(sync_function, item) for item in data
        ]
        yield futures
    finally:
        thread_pool.shutdown(wait=True)