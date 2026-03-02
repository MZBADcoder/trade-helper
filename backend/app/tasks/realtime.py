from __future__ import annotations

import asyncio
import logging
import signal

from app.application.container import (
    build_stock_market_realtime_publisher,
    shutdown_stock_market_realtime_publisher,
)

logger = logging.getLogger(__name__)


async def run_realtime_publisher() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    logger.info("Realtime task starting")

    def _stop_for_signal(sig_name: str) -> None:
        logger.info("Realtime task received signal %s, stopping", sig_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop_for_signal, sig.name)
        except NotImplementedError:
            continue

    try:
        publisher = build_stock_market_realtime_publisher()
        await publisher.run(stop_event=stop_event)
    finally:
        await shutdown_stock_market_realtime_publisher()
        logger.info("Realtime task stopped")


def main() -> None:
    asyncio.run(run_realtime_publisher())


if __name__ == "__main__":
    main()
