from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_market_data_service, get_options_service
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


@dataclass(slots=True)
class FakeOptionExpiration:
    date: str
    days_to_expiration: int
    contract_count: int


@dataclass(slots=True)
class FakeOptionExpirationsResult:
    underlying: str
    expirations: list[FakeOptionExpiration]
    source: str
    updated_at: datetime


@dataclass(slots=True)
class FakeOptionChainItem:
    option_ticker: str
    option_type: str
    strike: float
    bid: float
    ask: float
    last: float
    iv: float
    volume: int
    open_interest: int
    updated_at: datetime
    source: str


@dataclass(slots=True)
class FakeOptionChainResult:
    underlying: str
    expiration: str
    items: list[FakeOptionChainItem]
    next_cursor: str | None


@dataclass(slots=True)
class FakeOptionQuote:
    bid: float
    ask: float
    last: float
    updated_at: datetime


@dataclass(slots=True)
class FakeOptionSession:
    open: float
    high: float
    low: float
    volume: int
    open_interest: int


@dataclass(slots=True)
class FakeOptionGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


@dataclass(slots=True)
class FakeOptionContract:
    option_ticker: str
    underlying: str
    expiration: str
    option_type: str
    strike: float
    multiplier: int
    quote: FakeOptionQuote
    session: FakeOptionSession
    greeks: FakeOptionGreeks | None
    source: str


class FakeMarketDataService:
    def __init__(self) -> None:
        self.list_bars_calls: list[dict] = []
        self.list_snapshots_calls: list[list[str]] = []
        self.bars_data_source = "DB_AGG_MIXED"
        self.bars_partial_range = False

    def list_snapshots(self, *, tickers: list[str]) -> list[FakeSnapshot]:
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

    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]:
        self.list_bars_calls.append(
            {
                "ticker": ticker,
                "timespan": timespan,
                "multiplier": multiplier,
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

    def list_bars_with_meta(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> FakeBarsResult:
        bars = self.list_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return FakeBarsResult(
            bars=bars,
            data_source=self.bars_data_source,
            partial_range=self.bars_partial_range,
        )


class FakeOptionsService:
    def list_expirations(
        self,
        *,
        underlying: str,
        limit: int = 12,
        include_expired: bool = False,
    ) -> FakeOptionExpirationsResult:
        _ = (limit, include_expired)
        return FakeOptionExpirationsResult(
            underlying=underlying,
            expirations=[
                FakeOptionExpiration(
                    date="2026-02-21",
                    days_to_expiration=11,
                    contract_count=184,
                )
            ],
            source="REST",
            updated_at=datetime(2026, 2, 10, 14, 32, 10, tzinfo=timezone.utc),
        )

    def list_chain(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None = None,
        strike_to: float | None = None,
        option_type: str = "all",
        limit: int = 200,
        cursor: str | None = None,
    ) -> FakeOptionChainResult:
        _ = (strike_from, strike_to, option_type, limit, cursor)
        return FakeOptionChainResult(
            underlying=underlying,
            expiration=expiration,
            items=[
                FakeOptionChainItem(
                    option_ticker="O:AAPL260221C00210000",
                    option_type="call",
                    strike=210.0,
                    bid=1.23,
                    ask=1.28,
                    last=1.25,
                    iv=0.312,
                    volume=1532,
                    open_interest=10421,
                    updated_at=datetime(2026, 2, 10, 14, 33, 2, tzinfo=timezone.utc),
                    source="REST",
                )
            ],
            next_cursor="eyJvZmZzZXQiOjIwMH0=",
        )

    def get_contract(self, *, option_ticker: str, include_greeks: bool = True) -> FakeOptionContract:
        greeks = (
            FakeOptionGreeks(delta=0.45, gamma=0.03, theta=-0.08, vega=0.11, iv=0.312)
            if include_greeks
            else None
        )
        return FakeOptionContract(
            option_ticker=option_ticker,
            underlying="AAPL",
            expiration="2026-02-21",
            option_type="call",
            strike=210.0,
            multiplier=100,
            quote=FakeOptionQuote(
                bid=1.23,
                ask=1.28,
                last=1.25,
                updated_at=datetime(2026, 2, 10, 14, 33, 2, tzinfo=timezone.utc),
            ),
            session=FakeOptionSession(
                open=1.51,
                high=1.58,
                low=1.11,
                volume=1532,
                open_interest=10421,
            ),
            greeks=greeks,
            source="REST",
        )


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
def options_service() -> FakeOptionsService:
    return FakeOptionsService()


@pytest.fixture
def api_client(
    market_data_service: FakeMarketDataService,
    options_service: FakeOptionsService,
) -> Generator[TestClient, None, None]:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[get_options_service] = lambda: options_service
    with TestClient(app) as client:
        yield client
