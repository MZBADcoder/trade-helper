from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisMarketEventPublisher:
    def __init__(self, *, redis_url: str, channel: str) -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._client: redis.Redis | None = None
        self._lock = asyncio.Lock()

    async def publish(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        client = await self._get_client()
        await client.publish(self._channel, message)

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    async def _get_client(self) -> redis.Redis:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = redis.from_url(self._redis_url, decode_responses=False)
            return self._client


class RedisMarketEventSubscriber:
    def __init__(self, *, redis_url: str, channel: str) -> None:
        self._redis_url = redis_url
        self._channel = channel

    async def listen(
        self,
        *,
        stop_event: asyncio.Event,
        on_message: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        client = redis.from_url(self._redis_url, decode_responses=False)
        pubsub = client.pubsub()
        await pubsub.subscribe(self._channel)
        try:
            while not stop_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue
                payload = _decode_message_payload(message.get("data"))
                if payload is None:
                    continue
                try:
                    await on_message(payload)
                except Exception:
                    logger.exception("Failed to handle redis market event payload")
        finally:
            try:
                await pubsub.unsubscribe(self._channel)
            finally:
                await pubsub.close()
                await client.aclose()


def _decode_message_payload(raw: object) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload

