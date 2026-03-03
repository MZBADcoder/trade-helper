from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import queue
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_auth_service, get_market_data_service, get_market_stream_hub, get_watchlist_service
from app.api.errors import install_api_error_handlers
from app.api.v1.endpoints import market_data_stream as stream_endpoint
from app.api.v1.router import api_router
from app.core.config import settings
from app.domain.auth.schemas import User
from app.domain.watchlist.schemas import WatchlistItem


@pytest.fixture(autouse=True)
def _reset_stream_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "market_stream_realtime_enabled", True)
    monkeypatch.setattr(settings, "market_stream_delay_minutes", 0)


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

    async def get_current_user_from_token(self, *, token: str) -> User:
        if token != self._valid_token:
            raise ValueError("AUTH_INVALID_TOKEN")
        return self._user


class FakeWsWatchlistService:
    def __init__(self, *, symbols: list[str]) -> None:
        self._symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]

    async def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _ = user_id
        return [WatchlistItem(ticker=symbol) for symbol in self._symbols]


class FakeStreamHub:
    def __init__(self) -> None:
        self.subscription_calls: list[dict[str, Any]] = []
        self.registered_connections: set[str] = set()
        self.unregistered_connections: set[str] = set()
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._status_message: str | None = None
        self._subscription_call_queue: queue.Queue[dict[str, Any]] = queue.Queue()

    def current_latency(self) -> str:
        return "delayed"

    def current_status_message(self) -> str | None:
        return self._status_message

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
        call = {
            "connection_id": connection_id,
            "symbols": set(symbols),
            "channels": set(channels),
        }
        self.subscription_calls.append(call)
        self._subscription_call_queue.put_nowait(call)

    def push(self, payload: dict[str, Any]) -> None:
        for queue in self._queues.values():
            queue.put_nowait(payload)

    def next_subscription_call(self, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        return self._subscription_call_queue.get(timeout=timeout_seconds)


class FakeMarketDataService:
    def __init__(self, *, stream_session_open: bool = True) -> None:
        self._stream_session_open = stream_session_open
        self.stream_session_delay_minutes: list[int] = []

    async def is_stream_session_open(self, *, delay_minutes: int) -> bool:
        self.stream_session_delay_minutes.append(delay_minutes)
        return self._stream_session_open


def _build_stream_test_client(
    *,
    watchlist_symbols: list[str],
    valid_token: str = "valid-token",
    stream_session_open: bool = True,
) -> tuple[TestClient, FakeStreamHub]:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    auth_service = FakeWsAuthService(valid_token=valid_token)
    watchlist_service = FakeWsWatchlistService(symbols=watchlist_symbols)
    market_data_service = FakeMarketDataService(stream_session_open=stream_session_open)
    stream_hub = FakeStreamHub()

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_watchlist_service] = lambda: watchlist_service
    app.dependency_overrides[get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[get_market_stream_hub] = lambda: stream_hub

    return TestClient(app), stream_hub


def _stream_path() -> str:
    return "/api/v1/market-data/stream"


def _bearer_ws_headers(*, token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def test_stream_rejects_missing_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(_stream_path()) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_rejects_cookie_token_without_origin() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers={"cookie": "token=valid-token"},
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4403


def test_stream_rejects_subprotocol_bearer_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers={"sec-websocket-protocol": "bearer, valid-token"},
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_rejects_query_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/market-data/stream?access_token=valid-token") as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_rejects_cookie_token_when_cors_uses_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cors_allow_origins", ["*"])

    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers={
                    "cookie": "token=valid-token",
                    "origin": "https://example.com",
                },
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4403


def test_stream_accepts_cookie_token_with_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cors_allow_origins", ["http://frontend.test"])

    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers={
                "cookie": "token=valid-token",
                "origin": "http://frontend.test",
            },
        ) as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"


def test_stream_status_reports_delayed_message_when_realtime_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "market_stream_realtime_enabled", False)
    monkeypatch.setattr(settings, "market_stream_delay_minutes", 0)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    stream_hub._status_message = "delayed 15min"
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"
            assert status_payload["data"]["latency"] == "delayed"
            assert status_payload["data"]["connection_state"] == "connected"
            assert status_payload["data"]["message"] == "delayed 15min"


def test_stream_status_reports_reconnecting_when_realtime_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "market_stream_realtime_enabled", True)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    stream_hub._status_message = "market stream subscriber crashed, retrying"
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"
            assert status_payload["data"]["latency"] == "delayed"
            assert status_payload["data"]["connection_state"] == "reconnecting"
            assert status_payload["data"]["message"] == "market stream subscriber crashed, retrying"


def test_stream_unregisters_connection_when_initial_send_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_send(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (args, kwargs)
        raise RuntimeError("send failed")

    monkeypatch.setattr(stream_endpoint, "_send_ws_json", broken_send)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(RuntimeError, match="send failed"):
            with client.websocket_connect(
                _stream_path(),
                headers=_bearer_ws_headers(token="valid-token"),
            ) as websocket:
                websocket.receive_json()

    assert stream_hub.registered_connections
    assert stream_hub.registered_connections == stream_hub.unregistered_connections


def test_stream_rejects_invalid_token() -> None:
    client, _ = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers=_bearer_ws_headers(token="bad-token"),
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4401


def test_stream_rejects_connection_when_market_session_is_closed() -> None:
    client, stream_hub = _build_stream_test_client(
        watchlist_symbols=["AAPL"],
        stream_session_open=False,
    )

    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers=_bearer_ws_headers(token="valid-token"),
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4409

    assert stream_hub.registered_connections == set()


def test_stream_enforces_watchlist_permissions() -> None:
    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
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


def test_stream_allows_quote_channel_when_realtime_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "market_stream_realtime_enabled", False)
    monkeypatch.setattr(settings, "market_stream_delay_minutes", 0)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
            _ = websocket.receive_json()
            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["AAPL"],
                    "channels": ["quote"],
                }
            )
            subscription = stream_hub.next_subscription_call()
            assert subscription["symbols"] == {"AAPL"}
            assert subscription["channels"] == {"quote"}


def test_stream_enforces_symbol_limit_per_connection() -> None:
    symbols = [_index_to_symbol(index) for index in range(101)]
    client, stream_hub = _build_stream_test_client(watchlist_symbols=symbols)

    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
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


def test_stream_rejects_connection_when_delay_mode_disables_ws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "market_stream_delay_minutes", 15)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                _stream_path(),
                headers=_bearer_ws_headers(token="valid-token"),
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 4410

    assert stream_hub.registered_connections == set()


def test_stream_pushes_quote_trade_aggregate_messages() -> None:
    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
            _ = websocket.receive_json()
            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["AAPL"],
                    "channels": ["quote", "trade", "aggregate"],
                }
            )
            subscription = stream_hub.next_subscription_call()
            assert subscription["symbols"] == {"AAPL"}
            assert subscription["channels"] == {"quote", "trade", "aggregate"}

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
    monkeypatch.setattr(settings, "market_stream_ping_interval_seconds", 1.0)
    monkeypatch.setattr(settings, "market_stream_ping_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "market_stream_ping_max_misses", 2)

    client, stream_hub = _build_stream_test_client(watchlist_symbols=["AAPL"])
    with client:
        with client.websocket_connect(
            _stream_path(),
            headers=_bearer_ws_headers(token="valid-token"),
        ) as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"

            ping_payload = websocket.receive_json()
            assert ping_payload["type"] == "system.ping"
            websocket.send_json({"action": "pong"})

            websocket.send_json(
                {
                    "action": "subscribe",
                    "symbols": ["AAPL"],
                    "channels": ["quote"],
                }
            )
            subscription = stream_hub.next_subscription_call()
            assert subscription["symbols"] == {"AAPL"}
            assert subscription["channels"] == {"quote"}


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
