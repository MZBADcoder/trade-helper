from __future__ import annotations

import asyncio
import threading

from app.tasks.async_runtime import _close_task_loop, run_async_task


async def _current_loop_id() -> int:
    return id(asyncio.get_running_loop())


def test_run_async_task_reuses_worker_loop() -> None:
    first_loop_id = run_async_task(_current_loop_id())
    second_loop_id = run_async_task(_current_loop_id())

    assert first_loop_id == second_loop_id

    _close_task_loop()


async def _sleep_and_get_loop_id() -> int:
    await asyncio.sleep(0.01)
    return id(asyncio.get_running_loop())


def test_run_async_task_serializes_concurrent_calls_on_shared_loop() -> None:
    barrier = threading.Barrier(2)
    results: list[int] = []
    errors: list[BaseException] = []

    def exercise() -> None:
        try:
            barrier.wait()
            results.append(run_async_task(_sleep_and_get_loop_id()))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=exercise) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(results) == 2
    assert len(set(results)) == 1

    _close_task_loop()
