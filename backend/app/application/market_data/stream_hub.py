from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any

from app.application.market_data.stream_policy import (
    SUPPORTED_STREAM_CHANNELS,
    delayed_latency_message,
    normalized_delay_minutes,
)
from app.infrastructure.streaming.redis_event_bus import RedisMarketEventSubscriber
from app.infrastructure.streaming.redis_topic_registry import RedisMarketTopicRegistry

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")
_TOPIC_BY_CHANNEL = {
    "quote": ("Q",),
    "trade": ("T",),
    "aggregate": ("A", "AM"),
}

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ConnectionState:
    user_id: int
    symbols: set[str]
    channels: set[str]
    queue: asyncio.Queue[dict[str, Any]]


class StockMarketStreamHub:
    def __init__(
        self,
        *,
        event_subscriber: RedisMarketEventSubscriber | None,
        topic_registry: RedisMarketTopicRegistry | None,
        instance_id: str,
        max_symbols_per_connection: int = 100,
        queue_size: int = 512,
        registry_refresh_seconds: int = 10,
        allowed_channels: set[str] | None = None,
        default_channels: set[str] | None = None,
        realtime_enabled: bool = True,
        delay_minutes: int = 15,
    ) -> None:
        self._event_subscriber = event_subscriber
        self._topic_registry = topic_registry
        self._instance_id = instance_id.strip() or "gateway"
        self._max_symbols = max_symbols_per_connection
        self._queue_size = max(64, queue_size)
        self._lock = asyncio.Lock()
        self._runtime_lock = asyncio.Lock()
        self._registry_sync_lock = asyncio.Lock()
        self._connections: dict[str, _ConnectionState] = {}
        self._topic_ref_count: dict[str, int] = {}
        self._registry_refresh_seconds = max(5, registry_refresh_seconds)
        self._allowed_channels = _normalize_supported_channels(allowed_channels or SUPPORTED_STREAM_CHANNELS)
        configured_default_channels = default_channels if default_channels is not None else self._allowed_channels
        self._default_channels = _normalize_default_channels(
            configured_default_channels,
            allowed_channels=self._allowed_channels,
        )
        self._realtime_enabled = bool(realtime_enabled)
        self._delay_minutes = normalized_delay_minutes(delay_minutes)

        self._listener_stop_event = asyncio.Event()
        self._listener_task: asyncio.Task[None] | None = None
        self._registry_stop_event = asyncio.Event()
        self._registry_task: asyncio.Task[None] | None = None
        self._latency = "delayed"
        self._status_message = (
            delayed_latency_message(delay_minutes=self._delay_minutes) if not self._realtime_enabled else None
        )

    def current_latency(self) -> str:
        return self._latency

    def current_status_message(self) -> str | None:
        return self._status_message

    async def shutdown(self) -> None:
        async with self._lock:
            self._connections.clear()
            self._topic_ref_count.clear()
        await self._sync_registry()
        await self._stop_runtime()

    async def register_connection(
        self,
        *,
        connection_id: str,
        user_id: int,
    ) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        state = _ConnectionState(
            user_id=user_id,
            symbols=set(),
            channels=set(self._default_channels),
            queue=queue,
        )
        should_start_runtime = False
        async with self._lock:
            self._connections[connection_id] = state
            should_start_runtime = len(self._connections) == 1
        if should_start_runtime:
            await self._ensure_runtime()
            await self._sync_registry()
        return queue

    async def unregister_connection(self, *, connection_id: str) -> None:
        has_connections = False
        async with self._lock:
            state = self._connections.pop(connection_id, None)
            if state is None:
                return
            previous_topics = _build_topics(symbols=state.symbols, channels=state.channels)
            _decrease_topic_refs(self._topic_ref_count, previous_topics)
            has_connections = bool(self._connections)

        await self._sync_registry()
        if not has_connections:
            self._set_delayed_state()
            await self._stop_runtime()
            async with self._lock:
                has_connections_after_stop = bool(self._connections)
            if has_connections_after_stop:
                await self._ensure_runtime()
                await self._sync_registry()

    async def set_connection_subscription(
        self,
        *,
        connection_id: str,
        symbols: set[str],
        channels: set[str],
    ) -> None:
        normalized_symbols = _normalize_symbols(symbols)
        normalized_channels = _normalize_channels(
            channels,
            allowed_channels=self._allowed_channels,
            default_channels=self._default_channels,
        )
        if len(normalized_symbols) > self._max_symbols:
            raise ValueError("STREAM_SUBSCRIPTION_LIMIT_EXCEEDED")

        remaining_topics: set[str] | None = None
        async with self._lock:
            state = self._connections.get(connection_id)
            if state is None:
                raise ValueError("STREAM_CONNECTION_NOT_FOUND")

            old_topics = _build_topics(symbols=state.symbols, channels=state.channels)
            state.symbols = normalized_symbols
            state.channels = normalized_channels
            new_topics = _build_topics(symbols=state.symbols, channels=state.channels)

            _decrease_topic_refs(self._topic_ref_count, old_topics.difference(new_topics))
            _increase_topic_refs(self._topic_ref_count, new_topics.difference(old_topics))
            remaining_topics = set(self._topic_ref_count.keys())

        if remaining_topics is not None:
            await self._ensure_runtime()
            await self._sync_registry()

    async def _run_subscriber(self) -> None:
        if self._event_subscriber is None:
            return
        retry_delay_seconds = 1
        while not self._listener_stop_event.is_set():
            try:
                await self._event_subscriber.listen(
                    stop_event=self._listener_stop_event,
                    on_message=self._handle_bus_message,
                )
                if self._listener_stop_event.is_set():
                    return
                logger.warning("Market stream redis subscriber stopped unexpectedly, restarting")
                self._set_delayed_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Market stream redis subscriber crashed")
                self._set_delayed_state()

            if self._listener_stop_event.is_set():
                return

            try:
                await asyncio.wait_for(
                    self._listener_stop_event.wait(),
                    timeout=retry_delay_seconds,
                )
            except asyncio.TimeoutError:
                retry_delay_seconds = min(retry_delay_seconds * 2, 30)
                continue
            return

    async def _run_registry_keepalive(self) -> None:
        while not self._registry_stop_event.is_set():
            await self._sync_registry()
            try:
                await asyncio.wait_for(
                    self._registry_stop_event.wait(),
                    timeout=self._registry_refresh_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _ensure_runtime(self) -> None:
        async with self._runtime_lock:
            if self._event_subscriber is not None and (
                self._listener_task is None or self._listener_task.done()
            ):
                self._listener_stop_event = asyncio.Event()
                self._listener_task = asyncio.create_task(self._run_subscriber())
            if self._topic_registry is not None and (
                self._registry_task is None or self._registry_task.done()
            ):
                self._registry_stop_event = asyncio.Event()
                self._registry_task = asyncio.create_task(self._run_registry_keepalive())

    async def _stop_runtime(self) -> None:
        async with self._runtime_lock:
            listener_task = self._listener_task
            registry_task = self._registry_task
            self._listener_task = None
            self._registry_task = None
            self._listener_stop_event.set()
            self._registry_stop_event.set()

        tasks = [task for task in (listener_task, registry_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if self._topic_registry is not None:
            try:
                await self._topic_registry.delete_instance(instance_id=self._instance_id)
            except Exception:
                logger.exception("Failed to delete redis topic registry key")

    async def _snapshot_topics(self) -> set[str]:
        async with self._lock:
            return set(self._topic_ref_count.keys())

    async def _sync_registry(self) -> None:
        if self._topic_registry is None:
            return
        async with self._registry_sync_lock:
            # Always sync latest snapshot under lock to avoid stale writes from older callers.
            latest_topics = await self._snapshot_topics()
            try:
                await self._topic_registry.update_topics(
                    instance_id=self._instance_id,
                    topics=latest_topics,
                )
            except Exception:
                logger.exception("Failed to sync redis topic registry")

    async def _handle_bus_message(self, payload: dict[str, Any]) -> None:
        message_type = str(payload.get("type", "")).strip().lower()
        if message_type == "system.status":
            if self._realtime_enabled:
                data = payload.get("data")
                if isinstance(data, dict):
                    latency = str(data.get("latency", "")).strip().lower()
                    if latency in {"real-time", "delayed"}:
                        self._latency = latency
                    message = data.get("message")
                    if isinstance(message, str) and message.strip():
                        self._status_message = message.strip()
                    else:
                        self._status_message = None
            else:
                payload = self._enforce_delayed_status(payload)
            await self._broadcast(payload)
            return

        if message_type == "system.error":
            await self._broadcast(payload)
            return

        if not message_type.startswith("market."):
            return

        channel = message_type.split(".", maxsplit=1)[1]
        if channel not in SUPPORTED_STREAM_CHANNELS or channel not in self._allowed_channels:
            return
        data = payload.get("data")
        if not isinstance(data, dict):
            return
        symbol = str(data.get("symbol", "")).strip().upper()
        if not symbol:
            return

        async with self._lock:
            connections = list(self._connections.values())
        for connection in connections:
            if symbol not in connection.symbols:
                continue
            if channel not in connection.channels:
                continue
            _enqueue_payload(connection.queue, payload)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            queues = [connection.queue for connection in self._connections.values()]
        for queue in queues:
            _enqueue_payload(queue, payload)

    def _set_delayed_state(self) -> None:
        self._latency = "delayed"
        self._status_message = (
            delayed_latency_message(delay_minutes=self._delay_minutes) if not self._realtime_enabled else None
        )

    def _enforce_delayed_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._set_delayed_state()
        data = payload.get("data")
        normalized_data = dict(data) if isinstance(data, dict) else {}
        normalized_data["latency"] = "delayed"
        normalized_data["connection_state"] = "disabled"
        normalized_data["message"] = delayed_latency_message(delay_minutes=self._delay_minutes)
        return {
            **payload,
            "data": normalized_data,
        }


def _normalize_symbols(symbols: set[str]) -> set[str]:
    normalized: set[str] = set()
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if not _TICKER_PATTERN.fullmatch(symbol):
            raise ValueError("STREAM_SYMBOL_NOT_ALLOWED")
        normalized.add(symbol)
    return normalized


def _normalize_channels(
    channels: set[str],
    *,
    allowed_channels: set[str],
    default_channels: set[str],
) -> set[str]:
    normalized = {str(item).strip().lower() for item in channels if str(item).strip()}
    if not normalized:
        return set(default_channels)
    if not normalized.issubset(SUPPORTED_STREAM_CHANNELS):
        raise ValueError("STREAM_INVALID_ACTION")
    if not normalized.issubset(allowed_channels):
        raise ValueError("STREAM_CHANNEL_NOT_ALLOWED")
    return normalized


def _normalize_supported_channels(channels: set[str]) -> set[str]:
    normalized = {str(item).strip().lower() for item in channels if str(item).strip()}
    if not normalized:
        raise ValueError("STREAM_CHANNEL_NOT_ALLOWED")
    if not normalized.issubset(SUPPORTED_STREAM_CHANNELS):
        raise ValueError("STREAM_INVALID_ACTION")
    return normalized


def _normalize_default_channels(
    channels: set[str],
    *,
    allowed_channels: set[str],
) -> set[str]:
    normalized = _normalize_supported_channels(channels)
    if not normalized.issubset(allowed_channels):
        raise ValueError("STREAM_CHANNEL_NOT_ALLOWED")
    return normalized


def _build_topics(*, symbols: set[str], channels: set[str]) -> set[str]:
    topics: set[str] = set()
    for symbol in symbols:
        for channel in channels:
            for prefix in _TOPIC_BY_CHANNEL.get(channel, ()):
                topics.add(f"{prefix}.{symbol}")
    return topics


def _increase_topic_refs(refs: dict[str, int], topics: set[str]) -> None:
    for topic in topics:
        refs[topic] = refs.get(topic, 0) + 1


def _decrease_topic_refs(refs: dict[str, int], topics: set[str]) -> None:
    for topic in topics:
        current = refs.get(topic, 0)
        if current <= 1:
            refs.pop(topic, None)
            continue
        refs[topic] = current - 1


def _enqueue_payload(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
    try:
        queue.put_nowait(payload)
        return
    except asyncio.QueueFull:
        pass

    try:
        queue.get_nowait()
    except asyncio.QueueEmpty:
        pass
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        return
