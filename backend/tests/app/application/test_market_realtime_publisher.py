from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.application.market_data.realtime_publisher import StockMarketRealtimePublisher
from app.application.market_data.stream_event_mapper import map_massive_event_to_market_message, to_iso_datetime


class FakeUpstreamClient:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.topics_history: list[set[str]] = []
        self.handlers: dict[str, Any] = {}

    def set_handlers(self, *, on_events: Any, on_status: Any) -> None:
        self.handlers["on_events"] = on_events
        self.handlers["on_status"] = on_status

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def set_topics(self, topics: set[str]) -> None:
        self.topics_history.append(set(topics))


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.closed = False

    async def publish(self, payload: dict[str, Any]) -> None:
        self.published.append(payload)

    async def close(self) -> None:
        self.closed = True


class FakeTopicRegistry:
    def __init__(self) -> None:
        self.closed = False

    async def collect_topics(self) -> set[str]:
        return set()

    async def close(self) -> None:
        self.closed = True


def test_map_massive_event_to_market_message_supports_stock_events() -> None:
    quote_payload = map_massive_event_to_market_message({"ev": "Q", "sym": "AAPL", "t": 1_739_969_400_000})
    trade_payload = map_massive_event_to_market_message(
        {"ev": "T", "sym": "AAPL", "t": 1_739_969_401_000, "p": 201.2}
    )
    aggregate_payload = map_massive_event_to_market_message(
        {
            "ev": "AM",
            "sym": "AAPL",
            "s": 1_739_969_400_000,
            "e": 1_739_969_460_000,
            "o": 201.0,
            "h": 201.4,
            "l": 200.8,
            "c": 201.3,
        }
    )

    assert quote_payload is not None
    assert quote_payload["type"] == "market.quote"
    assert quote_payload["data"]["symbol"] == "AAPL"

    assert trade_payload is not None
    assert trade_payload["type"] == "market.trade"
    assert trade_payload["data"]["price"] == 201.2

    assert aggregate_payload is not None
    assert aggregate_payload["type"] == "market.aggregate"
    assert aggregate_payload["data"]["timespan"] == "minute"


def test_realtime_publisher_reconciles_upstream_topics() -> None:
    async def scenario() -> None:
        upstream = FakeUpstreamClient()
        publisher = FakeEventPublisher()
        registry = FakeTopicRegistry()
        service = StockMarketRealtimePublisher(
            upstream_client=upstream,
            event_publisher=publisher,
            topic_registry=registry,
            reconcile_interval_seconds=1,
        )

        await service._reconcile_upstream({"Q.AAPL", "T.AAPL"})
        await service._reconcile_upstream(set())
        await service.shutdown()

        assert upstream.start_calls == 1
        assert upstream.stop_calls >= 1
        assert {"Q.AAPL", "T.AAPL"} in upstream.topics_history
        assert set() in upstream.topics_history
        assert publisher.closed is True
        assert registry.closed is True

    asyncio.run(scenario())


def test_realtime_publisher_without_upstream_publishes_unavailable_error() -> None:
    async def scenario() -> None:
        publisher = FakeEventPublisher()
        registry = FakeTopicRegistry()
        service = StockMarketRealtimePublisher(
            upstream_client=None,
            event_publisher=publisher,
            topic_registry=registry,
            reconcile_interval_seconds=1,
        )

        stop_event = asyncio.Event()
        task = asyncio.create_task(service.run(stop_event=stop_event))
        await asyncio.sleep(0.02)
        stop_event.set()
        await task

        assert any(
            item.get("type") == "system.error"
            and item.get("data", {}).get("code") == "STREAM_UPSTREAM_UNAVAILABLE"
            for item in publisher.published
        )
        assert publisher.closed is True
        assert registry.closed is True

    asyncio.run(scenario())


def test_realtime_publisher_publishes_market_events_and_status() -> None:
    async def scenario() -> None:
        upstream = FakeUpstreamClient()
        publisher = FakeEventPublisher()
        registry = FakeTopicRegistry()
        service = StockMarketRealtimePublisher(
            upstream_client=upstream,
            event_publisher=publisher,
            topic_registry=registry,
            reconcile_interval_seconds=1,
        )

        await service._handle_upstream_events(
            [
                {"ev": "Q", "sym": "AAPL", "t": 1_739_969_400_000},
                {"ev": "T", "sym": "AAPL", "t": 1_739_969_401_000, "p": 201.2},
                {"ev": "AM", "sym": "AAPL", "s": 1_739_969_400_000, "e": 1_739_969_460_000, "c": 201.3},
            ]
        )
        await service._handle_upstream_status("connected", None)
        await service._handle_upstream_status("error", "upstream disconnected")

        published_types = [item["type"] for item in publisher.published]
        assert "market.quote" in published_types
        assert "market.trade" in published_types
        assert "market.aggregate" in published_types
        assert published_types.count("system.status") >= 2
        assert "system.error" in published_types

    asyncio.run(scenario())


def test_to_iso_datetime_handles_microseconds_timestamp() -> None:
    microseconds_value = 1_739_969_400_123_456
    expected = datetime.fromtimestamp(microseconds_value / 1_000_000, tz=timezone.utc)
    assert to_iso_datetime(microseconds_value) == expected.isoformat().replace("+00:00", "Z")
