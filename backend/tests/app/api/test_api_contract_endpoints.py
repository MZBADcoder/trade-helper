from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_market_data_service, get_options_service
from app.api.errors import install_api_error_handlers
from app.api.v1.router import api_router
from app.domain.auth.schemas import User
from app.domain.market_data.schemas import MarketBar


@dataclass(slots=True)
class _FakeSnapshot:
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
class _FakeOptionExpiration:
    date: str
    days_to_expiration: int
    contract_count: int


@dataclass(slots=True)
class _FakeOptionExpirationsResult:
    underlying: str
    expirations: list[_FakeOptionExpiration]
    source: str
    updated_at: datetime


@dataclass(slots=True)
class _FakeOptionChainItem:
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
class _FakeOptionChainResult:
    underlying: str
    expiration: str
    items: list[_FakeOptionChainItem]
    next_cursor: str | None


@dataclass(slots=True)
class _FakeOptionQuote:
    bid: float
    ask: float
    last: float
    updated_at: datetime


@dataclass(slots=True)
class _FakeOptionSession:
    open: float
    high: float
    low: float
    volume: int
    open_interest: int


@dataclass(slots=True)
class _FakeOptionGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


@dataclass(slots=True)
class _FakeOptionContract:
    option_ticker: str
    underlying: str
    expiration: str
    option_type: str
    strike: float
    multiplier: int
    quote: _FakeOptionQuote
    session: _FakeOptionSession
    greeks: _FakeOptionGreeks | None
    source: str


class _FakeMarketDataService:
    def __init__(self) -> None:
        self.list_bars_calls: list[dict] = []
        self.list_snapshots_calls: list[list[str]] = []

    def list_snapshots(self, *, tickers: list[str]) -> list[_FakeSnapshot]:
        self.list_snapshots_calls.append(tickers)
        now = datetime(2026, 2, 10, 14, 31, 22, tzinfo=timezone.utc)
        return [
            _FakeSnapshot(
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


class _FakeOptionsService:
    def list_expirations(
        self,
        *,
        underlying: str,
        limit: int = 12,
        include_expired: bool = False,
    ) -> _FakeOptionExpirationsResult:
        _ = include_expired
        return _FakeOptionExpirationsResult(
            underlying=underlying,
            expirations=[
                _FakeOptionExpiration(
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
    ) -> _FakeOptionChainResult:
        _ = (strike_from, strike_to, option_type, limit, cursor)
        return _FakeOptionChainResult(
            underlying=underlying,
            expiration=expiration,
            items=[
                _FakeOptionChainItem(
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

    def get_contract(self, *, option_ticker: str, include_greeks: bool = True) -> _FakeOptionContract:
        greeks = (
            _FakeOptionGreeks(delta=0.45, gamma=0.03, theta=-0.08, vega=0.11, iv=0.312)
            if include_greeks
            else None
        )
        return _FakeOptionContract(
            option_ticker=option_ticker,
            underlying="AAPL",
            expiration="2026-02-21",
            option_type="call",
            strike=210.0,
            multiplier=100,
            quote=_FakeOptionQuote(
                bid=1.23,
                ask=1.28,
                last=1.25,
                updated_at=datetime(2026, 2, 10, 14, 33, 2, tzinfo=timezone.utc),
            ),
            session=_FakeOptionSession(
                open=1.51,
                high=1.58,
                low=1.11,
                volume=1532,
                open_interest=10421,
            ),
            greeks=greeks,
            source="REST",
        )


def _fake_user() -> User:
    now = datetime(2026, 2, 10, 14, 0, 0, tzinfo=timezone.utc)
    return User(
        id=1,
        email="trader@example.com",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=now,
    )


def _build_client() -> tuple[TestClient, _FakeMarketDataService]:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    market_data_service = _FakeMarketDataService()
    options_service = _FakeOptionsService()

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[get_options_service] = lambda: options_service

    return TestClient(app), market_data_service


def test_snapshots_returns_contract_payload() -> None:
    client, market_data_service = _build_client()

    response = client.get("/api/v1/market-data/snapshots", params={"tickers": "AAPL,NVDA"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["ticker"] == "AAPL"
    assert payload["items"][0]["source"] == "REST"
    assert market_data_service.list_snapshots_calls == [["AAPL", "NVDA"]]


def test_snapshots_rejects_too_many_tickers() -> None:
    client, _ = _build_client()
    tickers = ",".join(f"T{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(51))

    response = client.get("/api/v1/market-data/snapshots", params={"tickers": tickers})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "MARKET_DATA_TOO_MANY_TICKERS"


def test_bars_requires_exactly_one_symbol() -> None:
    client, _ = _build_client()

    required = client.get("/api/v1/market-data/bars", params={"timespan": "day"})
    conflict = client.get(
        "/api/v1/market-data/bars",
        params={
            "ticker": "AAPL",
            "option_ticker": "O:AAPL260221C00210000",
            "timespan": "day",
        },
    )

    assert required.status_code == 400
    assert required.json()["error"]["code"] == "MARKET_DATA_SYMBOL_REQUIRED"
    assert conflict.status_code == 400
    assert conflict.json()["error"]["code"] == "MARKET_DATA_SYMBOL_CONFLICT"


def test_bars_success_sets_contract_headers() -> None:
    client, service = _build_client()

    response = client.get(
        "/api/v1/market-data/bars",
        params={
            "ticker": "AAPL",
            "timespan": "minute",
            "multiplier": 1,
            "from": "2026-02-09",
            "to": "2026-02-10",
            "limit": 100,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Data-Source"] in {"CACHE", "REST", "DB"}
    assert response.headers["X-Partial-Range"] in {"true", "false"}
    assert service.list_bars_calls[0]["ticker"] == "AAPL"


def test_options_expirations_respects_limit_range() -> None:
    client, _ = _build_client()

    invalid = client.get("/api/v1/options/expirations", params={"underlying": "AAPL", "limit": 37})
    valid = client.get("/api/v1/options/expirations", params={"underlying": "AAPL"})

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "OPTIONS_INVALID_LIMIT"
    assert valid.status_code == 200
    assert valid.json()["underlying"] == "AAPL"


def test_options_chain_rejects_invalid_strike_range() -> None:
    client, _ = _build_client()

    response = client.get(
        "/api/v1/options/chain",
        params={
            "underlying": "AAPL",
            "expiration": "2026-02-21",
            "strike_from": 220,
            "strike_to": 200,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OPTIONS_INVALID_STRIKE_RANGE"


def test_options_contract_include_greeks_toggle() -> None:
    client, _ = _build_client()

    with_greeks = client.get("/api/v1/options/contracts/O:AAPL260221C00210000")
    without_greeks = client.get(
        "/api/v1/options/contracts/O:AAPL260221C00210000",
        params={"include_greeks": "false"},
    )

    assert with_greeks.status_code == 200
    assert with_greeks.json()["greeks"]["delta"] == 0.45
    assert without_greeks.status_code == 200
    assert without_greeks.json()["greeks"] is None
