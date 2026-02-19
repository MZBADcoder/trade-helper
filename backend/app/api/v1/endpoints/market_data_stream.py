from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_auth_service, get_market_stream_hub, get_watchlist_service
from app.application.auth.service import AuthApplicationService
from app.application.market_data.stream_hub import StockMarketStreamHub
from app.application.market_data.stream_session import MarketStreamSession, parse_stream_action
from app.application.watchlist.service import WatchlistApplicationService
from app.core.config import settings

router = APIRouter()


@router.websocket("/stream")
async def market_data_stream(
    websocket: WebSocket,
    hub: StockMarketStreamHub = Depends(get_market_stream_hub),
    auth_service: AuthApplicationService = Depends(get_auth_service),
    watchlist_service: WatchlistApplicationService = Depends(get_watchlist_service),
) -> None:
    token, from_cookie = _extract_ws_token(websocket)
    await websocket.accept()
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    if from_cookie and not _is_ws_origin_allowed(websocket):
        await websocket.close(code=4403, reason="origin not allowed")
        return

    try:
        current_user = auth_service.get_current_user_from_token(token=token)
    except ValueError:
        await websocket.close(code=4401, reason="invalid token")
        return

    connection_id = uuid4().hex
    event_queue = await hub.register_connection(connection_id=connection_id, user_id=current_user.id)
    send_lock = asyncio.Lock()
    session = MarketStreamSession(
        max_symbols=settings.market_stream_max_symbols_per_connection,
        ping_interval_seconds=settings.market_stream_ping_interval_seconds,
        ping_timeout_seconds=settings.market_stream_ping_timeout_seconds,
        ping_max_misses=settings.market_stream_ping_max_misses,
    )

    await _send_ws_json(
        websocket,
        payload=_system_status(
            latency=hub.current_latency(),
            connection_state="connected",
        ),
        send_lock=send_lock,
    )

    async def receive_loop() -> None:
        while True:
            raw = await websocket.receive_text()
            parsed = parse_stream_action(raw)
            if parsed is None:
                await _send_ws_json(
                    websocket,
                    payload=_system_error(
                        code="STREAM_INVALID_ACTION",
                        message="invalid websocket payload",
                    ),
                    send_lock=send_lock,
                )
                continue

            allowed_symbols = (
                _allowed_watchlist_symbols(
                    service=watchlist_service,
                    user_id=current_user.id,
                )
                if parsed.action == "subscribe"
                else set()
            )
            outcome = session.apply_action(
                parsed,
                allowed_symbols=allowed_symbols,
                now=time.monotonic(),
            )
            if outcome.error is not None:
                await _send_ws_json(
                    websocket,
                    payload=_system_error(
                        code=outcome.error.code,
                        message=outcome.error.message,
                    ),
                    send_lock=send_lock,
                )
                continue

            if not outcome.changed:
                continue

            try:
                await hub.set_connection_subscription(
                    connection_id=connection_id,
                    symbols=outcome.symbols,
                    channels=outcome.channels,
                )
            except ValueError as exc:
                await _send_ws_json(
                    websocket,
                    payload=_system_error(
                        code=str(exc),
                        message="failed to update subscriptions",
                    ),
                    send_lock=send_lock,
                )

    async def send_loop() -> None:
        while True:
            payload = await event_queue.get()
            await _send_ws_json(websocket, payload=payload, send_lock=send_lock)

    async def heartbeat_loop() -> None:
        while True:
            decision = session.heartbeat_decision(now=time.monotonic())
            if decision.should_close:
                await websocket.close(code=4408, reason="ping timeout")
                return

            if decision.should_send_ping:
                await _send_ws_json(
                    websocket,
                    payload=_system_ping(),
                    send_lock=send_lock,
                )
                session.mark_ping_sent(sent_at=time.monotonic())

            await asyncio.sleep(decision.sleep_seconds)

    tasks = [
        asyncio.create_task(receive_loop()),
        asyncio.create_task(send_loop()),
        asyncio.create_task(heartbeat_loop()),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is None or isinstance(exc, WebSocketDisconnect):
                continue
            raise exc
    except WebSocketDisconnect:
        return
    finally:
        for task in tasks:
            if task.done():
                continue
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await hub.unregister_connection(connection_id=connection_id)


def _extract_ws_token(websocket: WebSocket) -> tuple[str | None, bool]:
    query_token = websocket.query_params.get("token")
    if query_token:
        return query_token.strip(), False

    cookie_token = websocket.cookies.get("token") or websocket.cookies.get("access_token")
    if cookie_token:
        return cookie_token.strip(), True

    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", maxsplit=1)[1].strip(), False

    subprotocol = websocket.headers.get("sec-websocket-protocol", "")
    if subprotocol:
        segments = [segment.strip() for segment in subprotocol.split(",") if segment.strip()]
        if len(segments) >= 2 and segments[0].lower() in {"bearer", "token"}:
            return segments[1], False
        if len(segments) == 1:
            return segments[0], False
    return None, False


def _is_ws_origin_allowed(websocket: WebSocket) -> bool:
    origin = (websocket.headers.get("origin") or "").strip()
    normalized_origin = _normalize_origin(origin)
    if normalized_origin is None:
        return False
    if "*" in settings.cors_allow_origins:
        return True

    allowed_origins = {
        normalized
        for normalized in (_normalize_origin(value) for value in settings.cors_allow_origins)
        if normalized is not None
    }
    return normalized_origin in allowed_origins


def _normalize_origin(value: str) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _allowed_watchlist_symbols(*, service: WatchlistApplicationService, user_id: int) -> set[str]:
    items = service.list_items(user_id=user_id)
    return {item.ticker.strip().upper() for item in items if item.ticker.strip()}


def _system_ping() -> dict[str, object]:
    return {
        "type": "system.ping",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {},
    }


def _system_status(*, latency: str, connection_state: str) -> dict[str, object]:
    return {
        "type": "system.status",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {
            "latency": latency,
            "connection_state": connection_state,
        },
    }


def _system_error(*, code: str, message: str) -> dict[str, object]:
    return {
        "type": "system.error",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {
            "code": code,
            "message": message,
        },
    }


async def _send_ws_json(
    websocket: WebSocket,
    *,
    payload: dict[str, Any],
    send_lock: asyncio.Lock,
) -> None:
    async with send_lock:
        await websocket.send_json(payload)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
