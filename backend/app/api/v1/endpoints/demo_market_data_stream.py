from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_demo_market_data_service
from app.application.demo_market.service import (
    DEMO_TICKER,
    DemoAggregateStreamEvent,
    DemoMarketDataApplicationService,
    DemoQuoteStreamEvent,
    DemoReplayWindow,
    DemoTradeStreamEvent,
)
from app.application.market_data.stream_policy import SUPPORTED_STREAM_CHANNELS
from app.application.market_data.stream_session import MarketStreamSession, StreamClientAction, parse_stream_action
from app.core.config import settings

router = APIRouter()
_STREAM_STEP_SECONDS = 1.0


@router.websocket("/market-data/stream")
async def demo_market_data_stream(
    websocket: WebSocket,
    service: DemoMarketDataApplicationService = Depends(get_demo_market_data_service),
) -> None:
    await websocket.accept()
    replay_window = service.replay_window()
    session = MarketStreamSession(
        max_symbols=1,
        ping_interval_seconds=settings.market_stream_ping_interval_seconds,
        ping_timeout_seconds=settings.market_stream_ping_timeout_seconds,
        ping_max_misses=settings.market_stream_ping_max_misses,
        allowed_channels=set(SUPPORTED_STREAM_CHANNELS),
        default_channels=set(SUPPORTED_STREAM_CHANNELS),
    )
    session.apply_action(
        StreamClientAction(
            action="subscribe",
            symbols={DEMO_TICKER},
            channels=set(),
        ),
        allowed_symbols={DEMO_TICKER},
        now=time.monotonic(),
    )

    send_lock = asyncio.Lock()
    tasks: list[asyncio.Task[None]] = []
    replay_step = 0
    try:
        await _send_ws_json(
            websocket,
            payload=_system_status(message=service.replay_status_message(window=replay_window)),
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

                outcome = session.apply_action(
                    parsed,
                    allowed_symbols={DEMO_TICKER},
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

        async def send_loop() -> None:
            nonlocal replay_step
            while True:
                symbols = session.symbols
                channels = session.channels
                if DEMO_TICKER in symbols and channels:
                    events = service.stream_events(
                        step=replay_step,
                        channels=channels,
                        window=replay_window,
                    )
                    payloads = [_to_ws_payload(item) for item in events]
                    for payload in payloads:
                        await _send_ws_json(websocket, payload=payload, send_lock=send_lock)
                    replay_step = (replay_step + 1) % max(replay_window.size, 1)
                await asyncio.sleep(_STREAM_STEP_SECONDS)

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


def _system_ping() -> dict[str, object]:
    return {
        "type": "system.ping",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {},
    }


def _system_status(*, message: str) -> dict[str, object]:
    return {
        "type": "system.status",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {
            "latency": "real-time",
            "connection_state": "connected",
            "message": message,
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


def _to_ws_payload(
    event: DemoQuoteStreamEvent | DemoTradeStreamEvent | DemoAggregateStreamEvent,
) -> dict[str, object]:
    if isinstance(event, DemoQuoteStreamEvent):
        return {
            "type": "market.quote",
            "ts": _utc_now_iso(),
            "source": "WS",
            "data": {
                "symbol": event.symbol,
                "event_ts": _iso_utc(event.event_at),
                "bid": event.bid,
                "ask": event.ask,
                "bid_size": event.bid_size,
                "ask_size": event.ask_size,
                "replay_index": event.replay_index,
            },
        }

    if isinstance(event, DemoTradeStreamEvent):
        return {
            "type": "market.trade",
            "ts": _utc_now_iso(),
            "source": "WS",
            "data": {
                "symbol": event.symbol,
                "event_ts": _iso_utc(event.event_at),
                "price": event.price,
                "last": event.last,
                "size": event.size,
                "replay_index": event.replay_index,
            },
        }

    return {
        "type": "market.aggregate",
        "ts": _utc_now_iso(),
        "source": "WS",
        "data": {
            "symbol": event.symbol,
            "event_ts": _iso_utc(event.event_at),
            "start_at": _iso_utc(event.start_at),
            "end_at": _iso_utc(event.end_at),
            "timespan": event.timespan,
            "multiplier": event.multiplier,
            "open": event.open,
            "high": event.high,
            "low": event.low,
            "close": event.close,
            "last": event.last,
            "volume": event.volume,
            "vwap": event.vwap,
            "replay_index": event.replay_index,
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


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
