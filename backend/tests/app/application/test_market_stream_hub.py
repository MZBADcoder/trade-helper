from __future__ import annotations

import asyncio
import time
from typing import Callable

import pytest

from app.application.market_data.stream_hub import StockMarketStreamHub


class FakeTopicRegistry:
    def __init__(self) -> None:
        self.updates: list[tuple[str, set[str]]] = []
        self.deleted_instances: list[str] = []

    async def update_topics(self, *, instance_id: str, topics: set[str]) -> None:
        self.updates.append((instance_id, set(topics)))

    async def delete_instance(self, *, instance_id: str) -> None:
        self.deleted_instances.append(instance_id)


class FlakySubscriber:
    def __init__(self) -> None:
        self.listen_calls = 0

    async def listen(self, *, stop_event: asyncio.Event, on_message: object) -> None:
        _ = on_message
        self.listen_calls += 1
        if self.listen_calls == 1:
            raise RuntimeError("subscriber failed")
        await stop_event.wait()


def test_stream_hub_fanout_respects_symbol_and_channel_from_bus() -> None:
    async def scenario() -> None:
        hub = StockMarketStreamHub(
            event_subscriber=None,
            topic_registry=None,
            instance_id="gw-test",
            max_symbols_per_connection=100,
            queue_size=32,
        )
        queue_1 = await hub.register_connection(connection_id="c1", user_id=1)
        queue_2 = await hub.register_connection(connection_id="c2", user_id=2)

        await hub.set_connection_subscription(
            connection_id="c1",
            symbols={"AAPL"},
            channels={"quote", "aggregate"},
        )
        await hub.set_connection_subscription(
            connection_id="c2",
            symbols={"MSFT"},
            channels={"quote"},
        )

        await hub._handle_bus_message(
            {
                "type": "market.quote",
                "ts": "2026-02-19T13:00:00Z",
                "source": "WS",
                "data": {
                    "symbol": "AAPL",
                    "event_ts": "2026-02-19T13:00:00Z",
                    "bid": 201.1,
                    "ask": 201.2,
                },
            }
        )
        await hub._handle_bus_message(
            {
                "type": "market.trade",
                "ts": "2026-02-19T13:00:01Z",
                "source": "WS",
                "data": {
                    "symbol": "MSFT",
                    "event_ts": "2026-02-19T13:00:01Z",
                    "price": 402.5,
                },
            }
        )
        await hub._handle_bus_message(
            {
                "type": "market.quote",
                "ts": "2026-02-19T13:00:02Z",
                "source": "WS",
                "data": {
                    "symbol": "MSFT",
                    "event_ts": "2026-02-19T13:00:02Z",
                    "bid": 402.4,
                    "ask": 402.6,
                },
            }
        )
        await hub._handle_bus_message(
            {
                "type": "market.aggregate",
                "ts": "2026-02-19T13:01:00Z",
                "source": "WS",
                "data": {
                    "symbol": "AAPL",
                    "event_ts": "2026-02-19T13:01:00Z",
                    "timespan": "minute",
                    "multiplier": 1,
                    "open": 201.0,
                    "high": 201.4,
                    "low": 200.8,
                    "close": 201.3,
                },
            }
        )

        queue_1_messages = [queue_1.get_nowait(), queue_1.get_nowait()]
        queue_2_messages = [queue_2.get_nowait()]

        assert [message["type"] for message in queue_1_messages] == [
            "market.quote",
            "market.aggregate",
        ]
        assert {message["data"]["symbol"] for message in queue_1_messages} == {"AAPL"}

        assert queue_2_messages[0]["type"] == "market.quote"
        assert queue_2_messages[0]["data"]["symbol"] == "MSFT"
        assert queue_2.empty()
        await hub.shutdown()

    asyncio.run(scenario())


def test_stream_hub_syncs_topics_to_registry() -> None:
    async def scenario() -> None:
        topic_registry = FakeTopicRegistry()
        hub = StockMarketStreamHub(
            event_subscriber=None,
            topic_registry=topic_registry,
            instance_id="gw-registry",
            max_symbols_per_connection=100,
            queue_size=32,
            registry_refresh_seconds=60,
        )
        await hub.register_connection(connection_id="c1", user_id=1)
        await hub.set_connection_subscription(
            connection_id="c1",
            symbols={"AAPL"},
            channels={"quote"},
        )
        await hub.unregister_connection(connection_id="c1")
        await hub.shutdown()

        assert any(instance_id == "gw-registry" and "Q.AAPL" in topics for instance_id, topics in topic_registry.updates)
        assert "gw-registry" in topic_registry.deleted_instances

    asyncio.run(scenario())


def test_stream_hub_broadcasts_system_status_and_updates_latency() -> None:
    async def scenario() -> None:
        hub = StockMarketStreamHub(
            event_subscriber=None,
            topic_registry=None,
            instance_id="gw-test",
            max_symbols_per_connection=100,
            queue_size=32,
        )
        await hub.register_connection(connection_id="c1", user_id=1)
        queue_2 = await hub.register_connection(connection_id="c2", user_id=2)

        await hub._handle_bus_message(
            {
                "type": "system.status",
                "ts": "2026-02-19T13:00:00Z",
                "source": "WS",
                "data": {
                    "latency": "real-time",
                    "connection_state": "connected",
                },
            }
        )
        assert hub.current_latency() == "real-time"
        queue_2_status = queue_2.get_nowait()
        assert queue_2_status["type"] == "system.status"

        await hub._handle_bus_message(
            {
                "type": "system.error",
                "ts": "2026-02-19T13:00:05Z",
                "source": "WS",
                "data": {
                    "code": "STREAM_UPSTREAM_UNAVAILABLE",
                    "message": "upstream disconnected",
                },
            }
        )
        queue_2_error = queue_2.get_nowait()
        assert queue_2_error["type"] == "system.error"
        await hub.shutdown()

    asyncio.run(scenario())


def test_stream_hub_enforces_connection_symbol_limit() -> None:
    async def scenario() -> None:
        hub = StockMarketStreamHub(
            event_subscriber=None,
            topic_registry=None,
            instance_id="gw-test",
            max_symbols_per_connection=2,
            queue_size=32,
        )
        await hub.register_connection(connection_id="c1", user_id=1)
        with pytest.raises(ValueError, match="STREAM_SUBSCRIPTION_LIMIT_EXCEEDED"):
            await hub.set_connection_subscription(
                connection_id="c1",
                symbols={"AAPL", "MSFT", "NVDA"},
                channels={"quote", "trade", "aggregate"},
            )
        await hub.shutdown()

    asyncio.run(scenario())


def test_stream_hub_restarts_subscriber_after_crash() -> None:
    async def scenario() -> None:
        subscriber = FlakySubscriber()
        hub = StockMarketStreamHub(
            event_subscriber=subscriber,
            topic_registry=None,
            instance_id="gw-retry",
            max_symbols_per_connection=100,
            queue_size=32,
        )

        await hub.register_connection(connection_id="c1", user_id=1)
        assert await _wait_until_async(lambda: subscriber.listen_calls >= 2, timeout_seconds=3.0)
        await hub.unregister_connection(connection_id="c1")
        await hub.shutdown()

    asyncio.run(scenario())


def test_stream_hub_delayed_mode_blocks_quote_and_forces_delayed_status() -> None:
    async def scenario() -> None:
        hub = StockMarketStreamHub(
            event_subscriber=None,
            topic_registry=None,
            instance_id="gw-delayed",
            max_symbols_per_connection=100,
            queue_size=32,
            allowed_channels={"trade", "aggregate"},
            default_channels={"trade", "aggregate"},
            realtime_enabled=False,
            delay_minutes=15,
        )

        queue = await hub.register_connection(connection_id="c1", user_id=1)
        await hub.set_connection_subscription(
            connection_id="c1",
            symbols={"AAPL"},
            channels=set(),
        )

        with pytest.raises(ValueError, match="STREAM_CHANNEL_NOT_ALLOWED"):
            await hub.set_connection_subscription(
                connection_id="c1",
                symbols={"AAPL"},
                channels={"quote"},
            )

        await hub._handle_bus_message(
            {
                "type": "system.status",
                "ts": "2026-02-19T13:00:00Z",
                "source": "WS",
                "data": {
                    "latency": "real-time",
                    "connection_state": "connected",
                },
            }
        )
        status_payload = queue.get_nowait()
        assert status_payload["data"]["latency"] == "delayed"
        assert status_payload["data"]["connection_state"] == "disabled"
        assert status_payload["data"]["message"] == "delayed 15min"
        assert hub.current_latency() == "delayed"

        await hub._handle_bus_message(
            {
                "type": "market.trade",
                "ts": "2026-02-19T13:00:01Z",
                "source": "WS",
                "data": {
                    "symbol": "AAPL",
                },
            }
        )
        trade_payload = queue.get_nowait()
        assert trade_payload["type"] == "market.trade"

        await hub._handle_bus_message(
            {
                "type": "market.quote",
                "ts": "2026-02-19T13:00:02Z",
                "source": "WS",
                "data": {
                    "symbol": "AAPL",
                },
            }
        )
        assert queue.empty()
        await hub.shutdown()

    asyncio.run(scenario())


async def _wait_until_async(predicate: Callable[[], bool], timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return predicate()
