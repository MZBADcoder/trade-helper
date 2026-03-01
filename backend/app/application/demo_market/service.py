from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
import random
import threading
from typing import Callable

from app.application.market_data.trading_calendar import MARKET_TIMEZONE, TradingCalendar
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.domain.watchlist.schemas import WatchlistItem

DEMO_TICKER = "AMD"
_DEMO_WINDOW_START = time(10, 0)
_DEMO_WINDOW_MINUTES = 30
_DEMO_DATA_SOURCE = "DEMO_MOCK"


@dataclass(slots=True)
class DemoBarsResult:
    bars: list[MarketBar]
    data_source: str
    partial_range: bool = False


@dataclass(slots=True)
class DemoReplayWindow:
    ticker: str
    trade_date: date
    start_at: datetime
    end_at: datetime
    bars: list[MarketBar]
    prev_close: float

    @property
    def size(self) -> int:
        return len(self.bars)


@dataclass(slots=True)
class DemoQuoteStreamEvent:
    symbol: str
    event_at: datetime
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    replay_index: int


@dataclass(slots=True)
class DemoTradeStreamEvent:
    symbol: str
    event_at: datetime
    price: float
    last: float
    size: float
    replay_index: int


@dataclass(slots=True)
class DemoAggregateStreamEvent:
    symbol: str
    event_at: datetime
    start_at: datetime
    end_at: datetime | None
    timespan: str
    multiplier: int
    open: float
    high: float
    low: float
    close: float
    last: float
    volume: float
    vwap: float | None
    replay_index: int


class DemoMarketDataApplicationService:
    def __init__(
        self,
        *,
        trading_calendar: TradingCalendar,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._trading_calendar = trading_calendar
        self._now_provider = now_provider or _utc_now
        self._window_lock = threading.Lock()
        self._cached_window: DemoReplayWindow | None = None

    async def list_watchlist(self) -> list[WatchlistItem]:
        return [WatchlistItem(ticker=DEMO_TICKER)]

    async def replay_window(self) -> DemoReplayWindow:
        await self._trading_calendar.ensure_holiday_cache()
        trade_date = self._recent_completed_trade_date()
        cached = self._cached_window
        if cached is not None and cached.trade_date == trade_date:
            return cached

        with self._window_lock:
            cached = self._cached_window
            if cached is not None and cached.trade_date == trade_date:
                return cached
            rebuilt = self._build_replay_window(trade_date=trade_date)
            self._cached_window = rebuilt
            return rebuilt

    async def replay_status_message(self, *, window: DemoReplayWindow | None = None) -> str:
        resolved = window or await self.replay_window()
        return (
            f"demo replay {resolved.trade_date.isoformat()} "
            f"{_DEMO_WINDOW_START.strftime('%H:%M')}-"
            f"{(datetime.combine(date.min, _DEMO_WINDOW_START) + timedelta(minutes=_DEMO_WINDOW_MINUTES)).time().strftime('%H:%M')} ET"
        )

    async def list_bars_with_meta(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        window: DemoReplayWindow | None = None,
    ) -> DemoBarsResult:
        normalized_ticker = _normalize_ticker(ticker)
        if normalized_ticker != DEMO_TICKER:
            raise ValueError("demo only supports AMD ticker")
        normalized_timespan = (timespan or "").strip().lower()
        if normalized_timespan != "minute":
            raise ValueError("demo bars only support minute timespan")
        if multiplier != 1:
            raise ValueError("demo bars only support multiplier=1")
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")

        resolved_window = window or await self.replay_window()
        bars = list(resolved_window.bars)

        if start_date is not None:
            bars = [bar for bar in bars if bar.start_at.date() >= start_date]
        if end_date is not None:
            bars = [bar for bar in bars if bar.start_at.date() <= end_date]
        if limit is not None:
            bars = bars[-limit:]

        return DemoBarsResult(
            bars=bars,
            data_source=_DEMO_DATA_SOURCE,
            partial_range=False,
        )

    async def list_snapshots(self, *, tickers: list[str], step: int = 0) -> list[MarketSnapshot]:
        return await self.list_snapshots_with_window(tickers=tickers, step=step, window=None)

    async def list_snapshots_with_window(
        self,
        *,
        tickers: list[str],
        step: int = 0,
        window: DemoReplayWindow | None,
    ) -> list[MarketSnapshot]:
        normalized = _normalize_tickers(tickers=tickers)
        if not normalized:
            raise ValueError("tickers must contain at least one symbol")
        invalid = [ticker for ticker in normalized if ticker != DEMO_TICKER]
        if invalid:
            blocked = ",".join(sorted(set(invalid)))
            raise ValueError(f"demo only supports AMD ticker: {blocked}")

        resolved_window = window or await self.replay_window()
        snapshot = await self.snapshot_for_step(step=step, window=resolved_window)
        return [snapshot]

    def replay_size(self) -> int:
        return _DEMO_WINDOW_MINUTES

    async def stream_events(
        self,
        *,
        step: int,
        channels: set[str],
        window: DemoReplayWindow | None = None,
    ) -> list[DemoQuoteStreamEvent | DemoTradeStreamEvent | DemoAggregateStreamEvent]:
        normalized_channels = {value.strip().lower() for value in channels if value.strip()}
        if not normalized_channels:
            return []

        resolved_window = window or await self.replay_window()
        frame = self._bar_for_step(window=resolved_window, step=step)
        frame_index = step % resolved_window.size
        snapshot = await self.snapshot_for_step(step=step, window=resolved_window)
        event_at = frame.start_at
        seed = _stable_seed(f"{resolved_window.trade_date.isoformat()}:{DEMO_TICKER}:{frame_index}")
        rng = random.Random(seed)
        spread = round(0.02 + rng.random() * 0.03, 4)
        bid = round(snapshot.last - spread / 2, 2)
        ask = round(snapshot.last + spread / 2, 2)
        trade_size = int(20 + rng.random() * 200)

        events: list[DemoQuoteStreamEvent | DemoTradeStreamEvent | DemoAggregateStreamEvent] = []
        if "quote" in normalized_channels:
            events.append(
                DemoQuoteStreamEvent(
                    symbol=DEMO_TICKER,
                    event_at=event_at,
                    bid=bid,
                    ask=ask,
                    bid_size=float(max(trade_size, 1)),
                    ask_size=float(max(trade_size - 1, 1)),
                    replay_index=frame_index,
                )
            )
        if "trade" in normalized_channels:
            events.append(
                DemoTradeStreamEvent(
                    symbol=DEMO_TICKER,
                    event_at=event_at,
                    price=frame.close,
                    last=frame.close,
                    size=float(trade_size),
                    replay_index=frame_index,
                )
            )
        if "aggregate" in normalized_channels:
            events.append(
                DemoAggregateStreamEvent(
                    symbol=DEMO_TICKER,
                    event_at=event_at,
                    start_at=frame.start_at,
                    end_at=frame.end_at,
                    timespan="minute",
                    multiplier=1,
                    open=frame.open,
                    high=frame.high,
                    low=frame.low,
                    close=frame.close,
                    last=frame.close,
                    volume=frame.volume,
                    vwap=frame.vwap,
                    replay_index=frame_index,
                )
            )

        return events

    async def snapshot_for_step(
        self,
        *,
        step: int,
        window: DemoReplayWindow | None = None,
    ) -> MarketSnapshot:
        resolved = window or await self.replay_window()
        frame_index = step % resolved.size
        frame = resolved.bars[frame_index]
        prefix = resolved.bars[: frame_index + 1]
        last = frame.close
        day_open = resolved.bars[0].open
        day_high = max(item.high for item in prefix)
        day_low = min(item.low for item in prefix)
        total_volume = int(sum(item.volume for item in prefix))
        change = last - resolved.prev_close
        change_pct = 0.0 if resolved.prev_close == 0 else (change / resolved.prev_close) * 100

        return MarketSnapshot(
            ticker=DEMO_TICKER,
            last=round(last, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 4),
            open=round(day_open, 2),
            high=round(day_high, 2),
            low=round(day_low, 2),
            volume=total_volume,
            updated_at=frame.start_at,
            market_status="open",
            source=_DEMO_DATA_SOURCE,
        )

    def _build_replay_window(self, *, trade_date: date) -> DemoReplayWindow:
        window_start_local = datetime.combine(trade_date, _DEMO_WINDOW_START, tzinfo=MARKET_TIMEZONE)
        window_end_local = window_start_local + timedelta(minutes=_DEMO_WINDOW_MINUTES)

        seed = _stable_seed(f"{trade_date.isoformat()}:{DEMO_TICKER}:window")
        rng = random.Random(seed)

        prev_close = round(118.0 + rng.random() * 8.0, 2)
        running_open = max(1.0, prev_close + rng.uniform(-0.9, 0.9))
        bars: list[MarketBar] = []

        for index in range(_DEMO_WINDOW_MINUTES):
            local_start = window_start_local + timedelta(minutes=index)
            oscillation = math.sin((index + 1) / 3.1) * 0.45 + math.sin((index + 1) / 1.7) * 0.22
            noise = rng.uniform(-0.24, 0.24)
            delta = oscillation + noise

            open_price = max(1.0, running_open)
            close_price = max(1.0, open_price + delta)
            high_price = max(open_price, close_price) + abs(rng.uniform(0.03, 0.32))
            low_price = max(0.01, min(open_price, close_price) - abs(rng.uniform(0.03, 0.32)))
            volume = float(int(82_000 + rng.randint(0, 42_000) + abs(delta) * 36_000))
            vwap = (open_price + high_price + low_price + close_price) / 4

            start_at_utc = local_start.astimezone(timezone.utc)
            end_at_utc = (local_start + timedelta(minutes=1)).astimezone(timezone.utc)
            bars.append(
                MarketBar(
                    ticker=DEMO_TICKER,
                    timespan="minute",
                    multiplier=1,
                    start_at=start_at_utc,
                    open=round(open_price, 2),
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    close=round(close_price, 2),
                    volume=volume,
                    vwap=round(vwap, 2),
                    trades=int(volume // 90 + rng.randint(80, 260)),
                    source=_DEMO_DATA_SOURCE,
                    end_at=end_at_utc,
                    is_final=True,
                )
            )
            running_open = close_price + rng.uniform(-0.12, 0.12)

        return DemoReplayWindow(
            ticker=DEMO_TICKER,
            trade_date=trade_date,
            start_at=window_start_local.astimezone(timezone.utc),
            end_at=window_end_local.astimezone(timezone.utc),
            bars=bars,
            prev_close=prev_close,
        )

    def _recent_completed_trade_date(self) -> date:
        now = self._now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now_et = now.astimezone(MARKET_TIMEZONE)
        candidate = now_et.date() - timedelta(days=1)
        return self._trading_calendar.align_on_or_before(target_date=candidate)

    @staticmethod
    def _bar_for_step(*, window: DemoReplayWindow, step: int) -> MarketBar:
        return window.bars[step % window.size]


def _normalize_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if not value:
        raise ValueError("ticker is required")
    return value


def _normalize_tickers(*, tickers: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = _normalize_ticker(raw)
        if ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(ticker)
    return normalized


def _stable_seed(value: str) -> int:
    seed = 0
    for char in value:
        seed = (seed * 131 + ord(char)) % 2_147_483_647
    return seed or 97


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)
