from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import pytest

import app.application.market_data.service as market_data_service_module
from app.application.market_data.service import MarketDataApplicationService
from app.application.market_data.trading_calendar import TradingCalendar
from app.domain.market_data.schemas import MarketBar
from app.domain.market_data.schemas import MarketSnapshot


class FakeUoW:
    market_data_repo = None
    auth_repo = None
    watchlist_repo = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeSnapshotRepo:
    def __init__(self, bars_by_ticker: dict[str, list[MarketBar]]) -> None:
        self._bars_by_ticker = bars_by_ticker

    async def list_recent_day_bars(self, *, ticker: str, limit: int = 2) -> list[MarketBar]:
        items = list(self._bars_by_ticker.get(ticker, []))
        items.sort(key=lambda bar: bar.start_at)
        if limit < 1:
            return []
        return items[-limit:]


class FakeUoWWithRepo(FakeUoW):
    def __init__(self, repo: FakeSnapshotRepo) -> None:
        self.market_data_repo = repo


class FakeDelayAwareTradingCalendar:
    def __init__(self, *, is_open: bool) -> None:
        self._is_open = is_open
        self.checked_points: list[datetime] = []
        self.ensure_called = 0

    async def ensure_holiday_cache(self) -> None:
        self.ensure_called += 1

    def is_in_trading_session(self, *, point: datetime) -> bool:
        self.checked_points.append(point)
        return self._is_open


class FakeMassiveSnapshotClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.payload: list[dict] = [
            {
                "ticker": "AAPL",
                "last": 203.12,
                "change": -0.85,
                "change_pct": -0.42,
                "open": 204.01,
                "high": 205.30,
                "low": 201.98,
                "volume": 48923112,
                "updated_at": "2026-02-10T14:31:22Z",
                "market_status": "open",
                "source": "REST",
            }
        ]

    async def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
        self.calls.append(tickers)
        return list(self.payload)

    async def list_market_holidays(self) -> list[dict]:
        return []


class FakeTradingDayCalendar:
    def __init__(self, *, trading_day: bool, market_open: bool = False) -> None:
        self._trading_day = trading_day
        self._market_open = market_open
        self.checked_dates: list[date] = []
        self.checked_points: list[datetime] = []
        self.ensure_called = 0

    async def ensure_holiday_cache(self) -> None:
        self.ensure_called += 1

    def is_trading_day(self, *, target_date: date) -> bool:
        self.checked_dates.append(target_date)
        return self._trading_day

    def is_in_trading_session(self, *, point: datetime) -> bool:
        self.checked_points.append(point)
        return self._market_open


class SnapshotDay:
    def __init__(self, *, open: float, high: float, low: float, volume: float) -> None:
        self.open = open
        self.high = high
        self.low = low
        self.volume = volume


class SnapshotLastTrade:
    def __init__(self, *, price: float) -> None:
        self.price = price


class SnapshotObject:
    def __init__(
        self,
        *,
        ticker: str,
        todays_change: float,
        todays_change_percent: float,
        updated: int,
        day: SnapshotDay,
        last_trade: SnapshotLastTrade,
    ) -> None:
        self.ticker = ticker
        self.todays_change = todays_change
        self.todays_change_percent = todays_change_percent
        self.updated = updated
        self.day = day
        self.last_trade = last_trade


async def test_list_snapshots_raises_upstream_unavailable_when_client_missing() -> None:
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=None)

    with pytest.raises(ValueError, match="MARKET_DATA_UPSTREAM_UNAVAILABLE"):
        await service.list_snapshots(tickers=["AAPL"])


def test_is_stream_session_open_applies_delay_before_calendar_check() -> None:
    calendar = FakeDelayAwareTradingCalendar(is_open=True)
    service = MarketDataApplicationService(
        uow=FakeUoW(),
        massive_client=None,
        trading_calendar=calendar,  # type: ignore[arg-type]
    )
    now = datetime(2026, 2, 24, 14, 55, tzinfo=timezone.utc)

    is_open = asyncio.run(
        service.is_stream_session_open(
            delay_minutes=15,
            now=now,
        )
    )

    assert is_open is True
    assert calendar.ensure_called == 1
    assert calendar.checked_points == [datetime(2026, 2, 24, 14, 40, tzinfo=timezone.utc)]


def test_list_snapshots_uses_market_trade_date_for_trading_day_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FrozenUtcDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return cls(2026, 2, 24, 0, 30, 0)
            return cls(2026, 2, 24, 0, 30, 0, tzinfo=tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FrozenUtcDateTime)
    calendar = FakeTradingDayCalendar(trading_day=True)
    client = FakeMassiveSnapshotClient()
    service = MarketDataApplicationService(
        uow=FakeUoW(),
        massive_client=client,
        trading_calendar=calendar,  # type: ignore[arg-type]
    )

    result = asyncio.run(service.list_snapshots(tickers=["AAPL"]))

    assert len(result) == 1
    assert calendar.ensure_called == 1
    assert calendar.checked_dates == [date(2026, 2, 23)]


async def test_list_snapshots_returns_mapped_domain_snapshots() -> None:
    client = FakeMassiveSnapshotClient()
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = await service.list_snapshots(tickers=["aapl", "AAPL", "nvda"])

    assert client.calls == [["AAPL", "NVDA"]]
    assert len(result) == 1
    item = result[0]
    assert isinstance(item, MarketSnapshot)
    assert item.ticker == "AAPL"
    assert item.last == pytest.approx(203.12)
    assert item.change == pytest.approx(-0.85)
    assert item.change_pct == pytest.approx(-0.42)
    assert item.updated_at == datetime(2026, 2, 10, 14, 31, 22, tzinfo=timezone.utc)
    assert item.source == "REST"


async def test_list_snapshots_rejects_invalid_ticker() -> None:
    client = FakeMassiveSnapshotClient()
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    with pytest.raises(ValueError, match="MARKET_DATA_INVALID_TICKERS"):
        await service.list_snapshots(tickers=["AA-PL"])


async def test_list_snapshots_resolves_unknown_market_status_from_delayed_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FrozenUtcDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return cls(2026, 2, 24, 14, 55, 0)
            return cls(2026, 2, 24, 14, 55, 0, tzinfo=tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FrozenUtcDateTime)
    monkeypatch.setattr(market_data_service_module.settings, "market_stream_delay_minutes", 15)
    calendar = FakeTradingDayCalendar(trading_day=True, market_open=True)
    client = FakeMassiveSnapshotClient()
    client.payload = [
        {
            "ticker": "AAPL",
            "last": 203.12,
            "change": -0.85,
            "change_pct": -0.42,
            "open": 204.01,
            "high": 205.30,
            "low": 201.98,
            "volume": 48923112,
            "updated_at": "2026-02-10T14:31:22Z",
            "market_status": "unknown",
            "source": "REST",
        }
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(),
        massive_client=client,
        trading_calendar=calendar,  # type: ignore[arg-type]
    )

    result = await service.list_snapshots(tickers=["AAPL"])

    assert result[0].market_status == "open"
    assert calendar.checked_points == [datetime(2026, 2, 24, 14, 40, 0, tzinfo=timezone.utc)]


async def test_list_snapshots_rejects_too_many_unique_tickers() -> None:
    client = FakeMassiveSnapshotClient()
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=client)
    tickers = [f"T{idx:02d}" for idx in range(51)]

    with pytest.raises(ValueError, match="MARKET_DATA_INVALID_TICKERS"):
        await service.list_snapshots(tickers=tickers)


async def test_list_snapshots_maps_rate_limit_error() -> None:
    class RateLimitedClient:
        async def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
            _ = tickers
            raise RuntimeError("429 rate limit exceeded")

        async def list_market_holidays(self) -> list[dict]:
            return []

    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=RateLimitedClient())

    with pytest.raises(ValueError, match="MARKET_DATA_RATE_LIMITED"):
        await service.list_snapshots(tickers=["AAPL"])


async def test_list_snapshots_returns_empty_list_for_empty_payload() -> None:
    client = FakeMassiveSnapshotClient()
    client.payload = []
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = await service.list_snapshots(tickers=["AAPL"])

    assert result == []


async def test_list_snapshots_maps_massive_ticker_snapshot_shape() -> None:
    client = FakeMassiveSnapshotClient()
    client.payload = [
        SnapshotObject(
            ticker="AAPL",
            todays_change=-0.85,
            todays_change_percent=-0.42,
            updated=1707575482000,
            day=SnapshotDay(open=204.01, high=205.30, low=201.98, volume=48923112),
            last_trade=SnapshotLastTrade(price=203.12),
        )
    ]
    service = MarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = await service.list_snapshots(tickers=["AAPL"])

    assert len(result) == 1
    item = result[0]
    assert item.ticker == "AAPL"
    assert item.last == pytest.approx(203.12)
    assert item.change == pytest.approx(-0.85)
    assert item.change_pct == pytest.approx(-0.42)
    assert item.open == pytest.approx(204.01)
    assert item.high == pytest.approx(205.30)
    assert item.low == pytest.approx(201.98)
    assert item.volume == 48923112
    assert item.updated_at == datetime(2024, 2, 10, 14, 31, 22, tzinfo=timezone.utc)


async def test_list_snapshots_uses_db_baseline_for_non_trading_day() -> None:
    prev_day = MarketBar(
        ticker="AAPL",
        timespan="day",
        multiplier=1,
        start_at=datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc),
        open=198.0,
        high=202.0,
        low=197.0,
        close=200.0,
        volume=1000,
    )
    latest_day = MarketBar(
        ticker="AAPL",
        timespan="day",
        multiplier=1,
        start_at=datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc),
        open=200.0,
        high=203.0,
        low=199.0,
        close=202.0,
        volume=1200,
    )
    repo = FakeSnapshotRepo({"AAPL": [prev_day, latest_day]})

    class ShouldNotCallMassiveClient:
        async def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
            raise AssertionError(f"Massive should not be called on non-trading day: {tickers}")

        async def list_market_holidays(self) -> list[dict]:
            return []

    service = MarketDataApplicationService(
        uow=FakeUoWWithRepo(repo),
        massive_client=ShouldNotCallMassiveClient(),
        trading_calendar=TradingCalendar(
            massive_client=None,
            today_provider=lambda: date(2026, 2, 22),  # Sunday
        ),
    )

    result = await service.list_snapshots(tickers=["AAPL"])

    assert len(result) == 1
    snapshot = result[0]
    assert snapshot.ticker == "AAPL"
    assert snapshot.last == pytest.approx(202.0)
    assert snapshot.change == pytest.approx(2.0)
    assert snapshot.change_pct == pytest.approx(1.0)
    assert snapshot.source == "DB"
