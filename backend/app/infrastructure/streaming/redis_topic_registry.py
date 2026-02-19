from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as redis


class RedisMarketTopicRegistry:
    def __init__(
        self,
        *,
        redis_url: str,
        key_prefix: str,
        ttl_seconds: int = 30,
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix.strip() or "market:stocks:subs"
        self._ttl_seconds = max(5, ttl_seconds)
        self._client: redis.Redis | None = None
        self._lock = asyncio.Lock()

    async def update_topics(self, *, instance_id: str, topics: set[str]) -> None:
        normalized = sorted({topic.strip() for topic in topics if topic and topic.strip()})
        payload = json.dumps({"topics": normalized}, separators=(",", ":"), ensure_ascii=False)
        client = await self._get_client()
        await client.set(self._key(instance_id), payload, ex=self._ttl_seconds)

    async def delete_instance(self, *, instance_id: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(instance_id))

    async def collect_topics(self) -> set[str]:
        topics: set[str] = set()
        client = await self._get_client()
        cursor = 0
        pattern = f"{self._key_prefix}:*"
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                values = await client.mget(keys)
                for value in values:
                    topics.update(_decode_topics(value))
            if cursor == 0:
                break
        return topics

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

    def _key(self, instance_id: str) -> str:
        normalized = instance_id.strip() or "unknown"
        return f"{self._key_prefix}:{normalized}"


def _decode_topics(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return set()
    if not isinstance(raw, str):
        return set()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(payload, dict):
        return set()
    topic_values = payload.get("topics")
    if not isinstance(topic_values, list):
        return set()
    return {str(topic).strip() for topic in topic_values if str(topic).strip()}

