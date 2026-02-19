from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_auth_service, get_market_stream_hub, get_watchlist_service
from app.api.errors import install_api_error_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.domain.auth.schemas import User
from app.domain.watchlist.schemas import WatchlistItem


class FakeWsAuthService:
    def __init__(self, *, valid_token: str = "valid-token") -> None:
        self._valid_token = valid_token
        self._user = User(
            id=1,
            email="trader@example.com",
            is_active=True,
            created_at=datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc),
            last_login_at=datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc),
        )

    def get_current_user_from_token(self, *, token: str) -> User:
        if token != self._valid_token:
            raise ValueError("AUTH_INVALID_TOKEN")
        return self._user


class FakeWsWatchlistService:
    def __init__(self, *, symbols: list[str]) -> None:
        self._symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]

    def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _ = user_id
        return [WatchlistItem(ticker=symbol) for symbol in self._symbols]


class FakeStreamHub:
    def __init__(self) -> None:
        self.subscription_calls: list[dict[str, Any]] = []
        self.registered_connections: set[str] = set()
        self.unregistered_connections: set[str] = set()
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

    def current_latency(self) -> str:
        return "delayed"

    async def register_connection(self, *, connection_id: str, user_id: int) -> asyncio.Queue[dict[str, Any]]:
        _ = user_id
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues[connection_id] = queue
        self.registered_connections.add(connection_id)
        return queue

    async def unregister_connection(self, *, connection_id: str) -> None:
        self.unregistered_connections.add(connection_id)
        self._queues.pop(connection_id, None)

    async def set_connection_subscription(
        self,
        *,
        connection_id: str,
        symbols: set[str],
        channels: set[str],
    ) -> None:
        if connection_id not in self._queues:
            raise ValueError("STREAM_CONNECTION_NOT_FOUND")
        self.subscription_calls.append(
            {
                "connection_id": connection_id,
                "symbols": set(symbols),
                "channels": set(channels),
            }
        )

    def push(self, payload: dict[str, Any]) -> None:
        for queue in self._queues.values():
            queue.put_nowait(payload)


def _build_stream_test_client(
    *,
    watchlist_symbols: list[str],
    valid_token: str = "valid-token",
) -> tuple[TestClient, FakeStreamHub]:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    auth_service = FakeWsAuthService(valid_token=valid_token)
    watchlist_service = FakeWsWatchlistService(symbols=watchlist_symbols)
    stream_hub = FakeStreamHub()

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_watchlist_service] = lambda: watchlist_service
    app.dependency_overrides[get_market_stream_hub] = lambda: stream_hub

    return TestClient(app), stream_hub


def test_stream_rejects_missing_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/market-data/stream") as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_rejects_cookie_token_without_origin() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/api/v1/market-data/stream",
                headers={"cookie": "token=valid-token"},
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4403


def test_stream_accepts_cookie_token_with_allowed_origin() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            "/api/v1/market-data/stream",
            headers={
                "cookie": "token=valid-token",
                "origin": settings.cors_allow_origins[0],
            },
        ) as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"


def test_stream_rejects_invalid_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/market-data/stream?token=bad-token") as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_enforces_watchlist_permissions() -> None:
    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect("/api/v1/market-data/stream?token=valid-token") as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"

            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["MSFT"],
                    "channels": ["quote", "trade", "aggregate"],
                }
            )
            error_payload = websocket.receive_json()
            assert error_payload["type"] == "system.error"
            assert error_payload["data"]["code"] == "STREAM_SYMBOL_NOT_ALLOWED"
            assert stream_hub.subscription_calls == []


def test_stream_enforces_symbol_limit_per_connection() -> None:
    symbols = [_index_to_symbol(index) for index in range(101)]
    client, stream_hub = _build_stream_test_client(watchlist_symbols=symbols)

    with client:
        with client.websocket_connect("/api/v1/market-data/stream?token=valid-token") as websocket:
            _ = websocket.receive_json()
            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": symbols,
                    "channels": ["quote", "trade", "aggregate"],
                }
            )
            error_payload = websocket.receive_json()
            assert error_payload["type"] == "system.error"
            assert error_payload["data"]["code"] == "STREAM_SUBSCRIPTION_LIMIT_EXCEEDED"
            assert stream_hub.subscription_calls == []


def test_stream_pushes_quote_trade_aggregate_messages() -> None:
    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect("/api/v1/market-data/stream?token=valid-token") as websocket:
            _ = websocket.receive_json()
            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["AAPL"],
                    "channels": ["quote", "trade", "aggregate"],
                }
            )
            assert _wait_until(lambda: len(stream_hub.subscription_calls) == 1)
            assert stream_hub.subscription_calls[0]["symbols"] == {"AAPL"}
            assert stream_hub.subscription_calls[0]["channels"] == {"quote", "trade", "aggregate"}

            stream_hub.push(
                {
                    "type": "market.quote",
                    "ts": "2026-02-19T13:00:00Z",
                    "source": "WS",
                    "data": {
                        "symbol": "AAPL",
                        "event_ts": "2026-02-19T13:00:00Z",
                        "bid": 200.1,
                        "ask": 200.2,
                        "last": 200.2,
                    },
                }
            )
            stream_hub.push(
                {
                    "type": "market.trade",
                    "ts": "2026-02-19T13:00:01Z",
                    "source": "WS",
                    "data": {
                        "symbol": "AAPL",
                        "event_ts": "2026-02-19T13:00:01Z",
                        "price": 200.25,
                        "last": 200.25,
                        "size": 15,
                    },
                }
            )
            stream_hub.push(
                {
                    "type": "market.aggregate",
                    "ts": "2026-02-19T13:00:05Z",
                    "source": "WS",
                    "data": {
                        "symbol": "AAPL",
                        "event_ts": "2026-02-19T13:00:05Z",
                        "timespan": "minute",
                        "multiplier": 1,
                        "open": 200.0,
                        "high": 200.4,
                        "low": 199.9,
                        "close": 200.3,
                        "last": 200.3,
                        "volume": 1000,
                    },
                }
            )

            messages = [websocket.receive_json() for _ in range(3)]
            assert [message["type"] for message in messages] == [
                "market.quote",
                "market.trade",
                "market.aggregate",
            ]
            assert {message["data"]["symbol"] for message in messages} == {"AAPL"}


def test_stream_heartbeat_ack_follows_server_ping_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "market_stream_ping_interval_seconds", 2)
    monkeypatch.setattr(settings, "market_stream_ping_timeout_seconds", 1)
    monkeypatch.setattr(settings, "market_stream_ping_max_misses", 2)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect("/api/v1/market-data/stream?token=valid-token") as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"

            for _ in range(3):
                ping_payload = websocket.receive_json()
                assert ping_payload["type"] == "system.ping"
                websocket.send_json({"action": "ping"})

            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["AAPL"],
                    "channels": ["quote"],
                }
            )
            assert _wait_until(lambda: len(stream_hub.subscription_calls) == 1, timeout_seconds=1.0)
            assert stream_hub.subscription_calls[0]["symbols"] == {"AAPL"}
            assert stream_hub.subscription_calls[0]["channels"] == {"quote"}


def _wait_until(predicate: Callable[[], bool], timeout_seconds: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _index_to_symbol(index: int) -> str:
    value = index
    chars: list[str] = []
    while True:
        value, remainder = divmod(value, 26)
        chars.append(chr(ord("A") + remainder))
        if value == 0:
            break
        value -= 1
    return "T" + "".join(reversed(chars))
