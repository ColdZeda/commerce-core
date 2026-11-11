"""并发跑任务的测试工具：真实线程、各自关连接，避免连接泄漏。"""

import queue
import threading

from django.db import connection


def run_threads(worker, count: int, concurrency: int | None = None) -> list:
    """跑 count 个任务、最多 concurrency 个线程同时跑；返回结果列表，顺序不保证。"""
    workers = min(concurrency or count, count)
    tasks: queue.Queue[int] = queue.Queue()
    for index in range(count):
        tasks.put(index)

    results: list = []
    lock = threading.Lock()

    def body():
        try:
            while True:
                try:
                    index = tasks.get_nowait()
                except queue.Empty:
                    return
                outcome = worker(index)
                with lock:
                    results.append(outcome)
        finally:
            connection.close()

    threads = [threading.Thread(target=body) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
        assert not thread.is_alive(), "线程超时未结束"
    return results
