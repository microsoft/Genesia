from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

from ..runtime import ModelGateway

WorkItem = TypeVar("WorkItem")


WorkResult = TypeVar("WorkResult")


def _run_bounded(
    items: list[WorkItem],
    worker: Callable[[WorkItem], WorkResult],
    max_workers: int,
):
    if max_workers == 1:
        for item in items:
            yield worker(item)
        return
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, item) for item in items]
        for future in as_completed(futures):
            yield future.result()


def _task_gateway(gateway: ModelGateway, max_workers: int):
    if max_workers == 1:
        return gateway, False
    fork = getattr(gateway, "fork", None)
    if not callable(fork):
        raise ValueError("Concurrent Persona generation requires a forkable model gateway")
    return fork(), True
