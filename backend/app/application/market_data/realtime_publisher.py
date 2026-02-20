from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.market_data.stream_policy import delayed_latency_message, normalized_delay_minutes
from app.application.market_data.stream_event_mapper import (
    build_system_error,
    build_system_status,
    map_massive_event_to_market_message,
)
from app.infrastructure.clients.massive_stream import MassiveStocksWebSocketClient
from app.infrastructure.streaming.redis_event_bus import RedisMarketEventPublisher
from app.infrastructure.streaming.redis_topic_registry import RedisMarketTopicRegistry

logger = logging.getLogger(__name__)


class StockMarketRealtimePublisher:
    def __init__(
        self,
        *,
        upstream_client: MassiveStocksWebSocketClient | None,
        event_publisher: RedisMarketEventPublisher,
        topic_registry: RedisMarketTopicRegistry,
        reconcile_interval_seconds: int = 2,
        realtime_enabled: bool = True,
        delay_minutes: int = 15,
    ) -> None:
        self._upstream_client = upstream_client
        self._event_publisher = event_publisher
        self._topic_registry = topic_registry
        self._reconcile_interval = max(1, reconcile_interval_seconds)
        self._realtime_enabled = bool(realtime_enabled)
        self._delay_minutes = normalized_delay_minutes(delay_minutes)
        self._delayed_message = delayed_latency_message(delay_minutes=self._delay_minutes)
        self._upstream_running = False

        if self._upstream_client is not None:
            self._upstream_client.set_handlers(
                on_events=self._handle_upstream_events,
                on_status=self._handle_upstream_status,
            )

    async def run(self, *, stop_event: asyncio.Event) -> None:
        try:
            if not self._realtime_enabled:
                await self._event_publisher.publish(
                    build_system_status(
                        latency="delayed",
                        connection_state="disabled",
                        message=self._delayed_message,
                    )
                )
                await stop_event.wait()
                return

            if self._upstream_client is None:
                await self._event_publisher.publish(
                    build_system_error(
                        code="STREAM_UPSTREAM_UNAVAILABLE",
                        message="massive stream client is not configured",
                    )
                )
                await stop_event.wait()
                return

            while not stop_event.is_set():
                topics = await self._topic_registry.collect_topics()
                await self._reconcile_upstream(topics)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._reconcile_interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._upstream_client is not None and self._upstream_running:
            await self._upstream_client.set_topics(set())
            await self._upstream_client.stop()
        self._upstream_running = False
        await self._topic_registry.close()
        await self._event_publisher.close()

    async def _reconcile_upstream(self, topics: set[str]) -> None:
        if self._upstream_client is None or not self._realtime_enabled:
            return

        if topics:
            if not self._upstream_running:
                await self._upstream_client.start()
                self._upstream_running = True
            await self._upstream_client.set_topics(topics)
            return

        if self._upstream_running:
            await self._upstream_client.set_topics(set())
            await self._upstream_client.stop()
            self._upstream_running = False
            await self._event_publisher.publish(
                build_system_status(
                    latency="delayed",
                    connection_state="idle",
                )
            )

    async def _handle_upstream_events(self, events: list[dict[str, Any]]) -> None:
        if not self._realtime_enabled:
            return
        for event in events:
            payload = map_massive_event_to_market_message(event)
            if payload is None:
                continue
            await self._event_publisher.publish(payload)

    async def _handle_upstream_status(self, state: str, message: str | None) -> None:
        if not self._realtime_enabled:
            await self._event_publisher.publish(
                build_system_status(
                    latency="delayed",
                    connection_state="disabled",
                    message=self._delayed_message,
                )
            )
            return
        latency = "real-time" if state == "connected" else "delayed"
        await self._event_publisher.publish(
            build_system_status(
                latency=latency,
                connection_state=state,
                message=message,
            )
        )
        if state in {"auth_failed", "error"}:
            await self._event_publisher.publish(
                build_system_error(
                    code="STREAM_UPSTREAM_UNAVAILABLE",
                    message=message or "upstream stream unavailable",
                )
            )
            return
        logger.debug("Upstream status changed to %s", state)
