from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class MassiveStocksWebSocketClient:
    def __init__(
        self,
        *,
        api_key: str,
        url: str = "wss://socket.massive.com/stocks",
        on_events: Callable[[list[dict[str, Any]]], Awaitable[None]] | None = None,
        on_status: Callable[[str, str | None], Awaitable[None]] | None = None,
        reconnect_max_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("Massive API key is not configured")

        self._api_key = api_key
        self._url = url
        self._on_events = on_events
        self._on_status = on_status
        self._reconnect_max_seconds = max(1.0, reconnect_max_seconds)

        self._lock = asyncio.Lock()
        self._desired_topics: set[str] = set()
        self._active_topics: set[str] = set()
        self._topic_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def set_handlers(
        self,
        *,
        on_events: Callable[[list[dict[str, Any]]], Awaitable[None]] | None,
        on_status: Callable[[str, str | None], Awaitable[None]] | None,
    ) -> None:
        self._on_events = on_events
        self._on_status = on_status

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        self._topic_event.set()

        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    async def set_topics(self, topics: set[str]) -> None:
        normalized = {item.strip() for item in topics if item and item.strip()}
        async with self._lock:
            self._desired_topics = normalized
        self._topic_event.set()

    async def _run_loop(self) -> None:
        reconnect_delay = 1.0

        while not self._stop_event.is_set():
            try:
                await self._emit_status("connecting", None)
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=1,
                    max_size=2 * 1024 * 1024,
                ) as websocket:
                    await self._authenticate(websocket)
                    await self._emit_status("connected", None)
                    reconnect_delay = 1.0
                    self._active_topics = set()
                    await self._reconcile_topics(websocket)

                    while not self._stop_event.is_set():
                        while self._topic_event.is_set():
                            self._topic_event.clear()
                            await self._reconcile_topics(websocket)

                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=1)
                        except asyncio.TimeoutError:
                            continue

                        payload = _parse_message_payload(raw)
                        if not payload:
                            continue

                        market_events: list[dict[str, Any]] = []
                        for item in payload:
                            if str(item.get("ev", "")).lower() == "status":
                                message = _to_str(item.get("message"))
                                status = _to_str(item.get("status")).lower()
                                if status == "auth_failed":
                                    await self._emit_status("auth_failed", message or "upstream auth failed")
                                    raise RuntimeError("upstream auth failed")
                                if status in {"error", "denied"}:
                                    await self._emit_status("error", message or "upstream status error")
                                continue
                            market_events.append(item)

                        if market_events and self._on_events is not None:
                            await self._on_events(market_events)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._emit_status("disconnected", str(exc))
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._reconnect_max_seconds)

        self._active_topics = set()

    async def _authenticate(self, websocket: websockets.ClientConnection) -> None:
        await websocket.send(json.dumps({"action": "auth", "params": self._api_key}))
        deadline = asyncio.get_running_loop().time() + 10.0

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise RuntimeError("upstream auth timeout")
            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            payload = _parse_message_payload(raw)
            if not payload:
                continue
            for item in payload:
                if str(item.get("ev", "")).lower() != "status":
                    continue
                status = _to_str(item.get("status")).lower()
                if status == "auth_success":
                    return
                if status == "auth_failed":
                    raise RuntimeError(_to_str(item.get("message")) or "upstream auth failed")

    async def _reconcile_topics(self, websocket: websockets.ClientConnection) -> None:
        async with self._lock:
            desired = set(self._desired_topics)

        to_subscribe = sorted(desired.difference(self._active_topics))
        to_unsubscribe = sorted(self._active_topics.difference(desired))

        if to_subscribe:
            await websocket.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "params": ",".join(to_subscribe),
                    }
                )
            )
        if to_unsubscribe:
            await websocket.send(
                json.dumps(
                    {
                        "action": "unsubscribe",
                        "params": ",".join(to_unsubscribe),
                    }
                )
            )
        self._active_topics = desired

    async def _emit_status(self, state: str, message: str | None) -> None:
        if self._on_status is None:
            return
        try:
            await self._on_status(state, message)
        except Exception:
            logger.exception("Failed to emit upstream status")


def _parse_message_payload(raw: str | bytes) -> list[dict[str, Any]]:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []

    if isinstance(decoded, dict):
        decoded = [decoded]
    if not isinstance(decoded, list):
        return []
    return [item for item in decoded if isinstance(item, dict)]


def _to_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
