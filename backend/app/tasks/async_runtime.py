from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import threading
from typing import TypeVar

from celery.signals import worker_process_shutdown

from app.application import container

_T = TypeVar("_T")
_task_loop: asyncio.AbstractEventLoop | None = None
_task_loop_lock = threading.Lock()


def run_async_task(awaitable: Awaitable[_T]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run_async_task must be called from a synchronous Celery task")

    with _task_loop_lock:
        loop = _get_task_loop()
        return loop.run_until_complete(awaitable)


def _get_task_loop() -> asyncio.AbstractEventLoop:
    global _task_loop
    if _task_loop is None or _task_loop.is_closed():
        _task_loop = asyncio.new_event_loop()
    return _task_loop


async def _shutdown_async_runtime() -> None:
    await container.shutdown_auth_login_throttle()
    await container.shutdown_market_stream_hub()
    await container.shutdown_stock_market_realtime_publisher()
    await container.shutdown_db_runtime()


@worker_process_shutdown.connect
def _close_task_loop(**_: object) -> None:
    global _task_loop

    with _task_loop_lock:
        loop = _task_loop
        _task_loop = None
        if loop is None or loop.is_closed():
            return

        try:
            loop.run_until_complete(_shutdown_async_runtime())
        finally:
            loop.close()
