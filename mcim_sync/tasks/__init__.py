from concurrent.futures import ThreadPoolExecutor


def create_tasks_pool(sync_function, data, max_workers, thread_name_prefix):
    thread_pool = ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix=thread_name_prefix
    )
    futures = [
        thread_pool.submit(sync_function, item) for item in data
    ]
    return thread_pool, futures
