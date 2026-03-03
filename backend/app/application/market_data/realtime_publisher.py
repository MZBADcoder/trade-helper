from __future__ import annotations

import asyncio
import logging
import time
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
        self._reconcile_cycles = 0
        self._fan_in_topics = 0
        self._last_reconciled_topics = -1
        self._events_in_total = 0
        self._events_mapped_total = 0
        self._events_published_total = 0
        self._events_dropped_total = 0
        self._progress_log_interval_seconds = 10
        self._last_progress_log_at = 0.0

        if self._upstream_client is not None:
            self._upstream_client.set_handlers(
                on_events=self._handle_upstream_events,
                on_status=self._handle_upstream_status,
            )

    async def run(self, *, stop_event: asyncio.Event) -> None:
        try:
            if self._upstream_client is None:
                logger.error("Market realtime publisher missing upstream client, fan in/out disabled")
                await self._event_publisher.publish(
                    build_system_error(
                        code="STREAM_UPSTREAM_UNAVAILABLE",
                        message="massive stream client is not configured",
                    )
                )
                await stop_event.wait()
                return

            logger.info(
                "Market realtime publisher started: reconcile_interval_seconds=%s realtime_enabled=%s delay_minutes=%s",
                self._reconcile_interval,
                self._realtime_enabled,
                self._delay_minutes,
            )
            while not stop_event.is_set():
                self._reconcile_cycles += 1
                try:
                    topics = await self._topic_registry.collect_topics()
                    await self._reconcile_upstream(topics)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Market realtime publisher reconcile loop failed")
                    await self._publish_reconcile_error()
                self._maybe_log_progress()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._reconcile_interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._maybe_log_progress(force=True)
            await self.shutdown()
            logger.info("Market realtime publisher stopped")

    async def shutdown(self) -> None:
        if self._upstream_client is not None and self._upstream_running:
            await self._upstream_client.set_topics(set())
            await self._upstream_client.stop()
        self._upstream_running = False
        await self._topic_registry.close()
        await self._event_publisher.close()

    async def _reconcile_upstream(self, topics: set[str]) -> None:
        if self._upstream_client is None:
            return

        topic_count = len(topics)
        self._fan_in_topics = topic_count
        if topics:
            action = "sync"
            if not self._upstream_running:
                await self._upstream_client.start()
                self._upstream_running = True
                action = "start"
            await self._upstream_client.set_topics(topics)
            if action == "start" or topic_count != self._last_reconciled_topics:
                logger.info(
                    "Market realtime fan in reconcile: action=%s topics=%s upstream_running=%s",
                    action,
                    topic_count,
                    self._upstream_running,
                )
            self._last_reconciled_topics = topic_count
            return

        if self._upstream_running:
            await self._upstream_client.set_topics(set())
            await self._upstream_client.stop()
            self._upstream_running = False
            logger.info(
                "Market realtime fan in reconcile: action=stop topics=0 upstream_running=%s",
                self._upstream_running,
            )
            await self._event_publisher.publish(
                build_system_status(
                    latency="delayed",
                    connection_state="idle",
                )
            )
        elif self._last_reconciled_topics != 0:
            logger.info(
                "Market realtime fan in reconcile: action=idle topics=0 upstream_running=%s",
                self._upstream_running,
            )
        self._last_reconciled_topics = 0

    async def _handle_upstream_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        mapped_count = 0
        dropped_count = 0
        published_count = 0
        for event in events:
            payload = map_massive_event_to_market_message(event)
            if payload is None:
                dropped_count += 1
                continue
            mapped_count += 1
            await self._event_publisher.publish(payload)
            published_count += 1

        self._events_in_total += len(events)
        self._events_mapped_total += mapped_count
        self._events_published_total += published_count
        self._events_dropped_total += dropped_count

        logger.debug(
            "Market realtime fan out batch: in=%s mapped=%s published=%s dropped=%s",
            len(events),
            mapped_count,
            published_count,
            dropped_count,
        )

    async def _handle_upstream_status(self, state: str, message: str | None) -> None:
        if state == "error" and _is_realtime_entitlement_error(message):
            await self._event_publisher.publish(
                build_system_status(
                    latency="delayed",
                    connection_state="degraded",
                    message=None,
                )
            )
            logger.warning(
                "MASSIVE_WS_ENTITLEMENT_MISSING: upstream denied websocket market-data entitlement. "
                "Realtime stream will stay in delayed mode and rely on REST polling."
            )
            return

        latency = "real-time" if self._realtime_enabled and state == "connected" else "delayed"
        status_message = _public_status_message(
            state=state,
            realtime_enabled=self._realtime_enabled,
            delayed_message=self._delayed_message,
        )
        await self._event_publisher.publish(
            build_system_status(
                latency=latency,
                connection_state=state,
                message=status_message,
            )
        )
        if state in {"auth_failed", "error"}:
            await self._event_publisher.publish(
                build_system_error(
                    code="STREAM_UPSTREAM_UNAVAILABLE",
                    message=_public_error_message(state=state),
                )
            )
            logger.warning(
                "Market realtime upstream status degraded: state=%s latency=%s",
                state,
                latency,
            )
            return
        logger.info(
            "Market realtime upstream status: state=%s latency=%s",
            state,
            latency,
        )

    async def _publish_reconcile_error(self) -> None:
        try:
            await self._event_publisher.publish(
                build_system_error(
                    code="STREAM_UPSTREAM_UNAVAILABLE",
                    message="market stream reconcile failed, retrying",
                )
            )
        except Exception:
            logger.exception("Failed to publish reconcile error event")

    def _maybe_log_progress(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_progress_log_at < self._progress_log_interval_seconds:
            return
        self._last_progress_log_at = now
        logger.info(
            (
                "Market realtime fan progress: cycles=%s fan_in_topics=%s upstream_running=%s "
                "events_in=%s mapped=%s published=%s dropped=%s"
            ),
            self._reconcile_cycles,
            self._fan_in_topics,
            self._upstream_running,
            self._events_in_total,
            self._events_mapped_total,
            self._events_published_total,
            self._events_dropped_total,
        )


def _is_realtime_entitlement_error(message: str | None) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False
    if "not authorized" in normalized:
        return True
    if "real-time data" in normalized and ("don't have access" in normalized or "do not have access" in normalized):
        return True
    return False


def _public_status_message(*, state: str, realtime_enabled: bool, delayed_message: str) -> str | None:
    if state == "connected" and not realtime_enabled:
        return delayed_message
    return None


def _public_error_message(*, state: str) -> str:
    if state == "auth_failed":
        return "upstream authentication failed"
    return "upstream stream unavailable"
