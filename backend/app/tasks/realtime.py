from __future__ import annotations

import asyncio
import signal

from app.application.container import (
    build_stock_market_realtime_publisher,
    shutdown_stock_market_realtime_publisher,
)


async def run_realtime_publisher() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            continue

    publisher = build_stock_market_realtime_publisher()
    await publisher.run(stop_event=stop_event)
    await shutdown_stock_market_realtime_publisher()


def main() -> None:
    asyncio.run(run_realtime_publisher())


if __name__ == "__main__":
    main()

