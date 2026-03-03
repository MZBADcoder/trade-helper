from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_market_data_service
from app.api.errors import install_api_error_handlers
from app.api.v1.router import api_router
from app.domain.auth.schemas import User
from app.domain.market_data.schemas import MarketBar


@dataclass(slots=True)
class FakeSnapshot:
    ticker: str
    last: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    updated_at: datetime
    market_status: str
    source: str


@dataclass(slots=True)
class FakeBarsResult:
    bars: list[MarketBar]
    data_source: str
    partial_range: bool


class FakeMarketDataService:
    def __init__(self) -> None:
        self.list_bars_calls: list[dict] = []
        self.list_snapshots_calls: list[list[str]] = []
        self.list_trading_days_calls: list[dict] = []
        self.bars_data_source = "DB_AGG_MIXED"
        self.bars_partial_range = False
        self.bars_error: Exception | None = None

    async def list_snapshots(self, *, tickers: list[str]) -> list[FakeSnapshot]:
        self.list_snapshots_calls.append(tickers)
        now = datetime(2026, 2, 10, 14, 31, 22, tzinfo=timezone.utc)
        return [
            FakeSnapshot(
                ticker="AAPL",
                last=203.12,
                change=-0.85,
                change_pct=-0.42,
                open=204.01,
                high=205.30,
                low=201.98,
                volume=48923112,
                updated_at=now,
                market_status="open",
                source="REST",
            )
        ]

    async def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        session: str = "regular",
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        enforce_range_limit: bool = False,
    ) -> list[MarketBar]:
        _ = enforce_range_limit
        self.list_bars_calls.append(
            {
                "ticker": ticker,
                "timespan": timespan,
                "multiplier": multiplier,
                "session": session,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            }
        )
        return [
            MarketBar(
                ticker=ticker,
                timespan=timespan,
                multiplier=multiplier,
                start_at=datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc),
                open=100.0,
                high=101.0,
                low=99.8,
                close=100.5,
                volume=12345,
                vwap=100.4,
                trades=321,
                source="REST",
            )
        ]

    async def list_bars_with_meta(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        session: str = "regular",
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        enforce_range_limit: bool = False,
    ) -> FakeBarsResult:
        if self.bars_error is not None:
            raise self.bars_error
        bars = await self.list_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            session=session,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            enforce_range_limit=enforce_range_limit,
        )
        return FakeBarsResult(
            bars=bars,
            data_source=self.bars_data_source,
            partial_range=self.bars_partial_range,
        )

    async def list_trading_days(
        self,
        *,
        end_date: date | None,
        count: int,
    ) -> list[date]:
        self.list_trading_days_calls.append({"end_date": end_date, "count": count})
        base = end_date or date(2026, 2, 24)
        return [base]


def fake_user() -> User:
    now = datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc)
    return User(
        id=1,
        email="trader@example.com",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=now,
    )


@pytest.fixture
def market_data_service() -> FakeMarketDataService:
    return FakeMarketDataService()


@pytest.fixture
def api_client(
    market_data_service: FakeMarketDataService,
) -> Generator[TestClient, None, None]:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_market_data_service] = lambda: market_data_service
    with TestClient(app) as client:
        yield client
