from __future__ import annotations

from app.application.market_data.errors import MarketDataRangeTooLargeError


def test_snapshots_returns_contract_payload(api_client, market_data_service) -> None:
    response = api_client.get("/api/v1/market-data/snapshots", params={"tickers": "AAPL,NVDA"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["ticker"] == "AAPL"
    assert payload["items"][0]["source"] == "REST"
    assert market_data_service.list_snapshots_calls == [["AAPL", "NVDA"]]


def test_snapshots_rejects_too_many_tickers(api_client) -> None:
    tickers = ",".join(f"T{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(51))

    response = api_client.get("/api/v1/market-data/snapshots", params={"tickers": tickers})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "MARKET_DATA_TOO_MANY_TICKERS"


def test_bars_requires_exactly_one_symbol(api_client) -> None:
    required = api_client.get("/api/v1/market-data/bars", params={"timespan": "day"})
    conflict = api_client.get(
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


def test_bars_rejects_invalid_timespan(api_client) -> None:
    response = api_client.get(
        "/api/v1/market-data/bars",
        params={
            "ticker": "AAPL",
            "timespan": "year",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MARKET_DATA_INVALID_TIMESPAN"


def test_bars_rejects_invalid_date_range(api_client) -> None:
    response = api_client.get(
        "/api/v1/market-data/bars",
        params={
            "ticker": "AAPL",
            "timespan": "day",
            "from": "2026-02-10",
            "to": "2026-02-10",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "MARKET_DATA_INVALID_RANGE"
    assert payload["error"]["details"] == {"from": "2026-02-10", "to": "2026-02-10"}


def test_bars_rejects_oversized_range(api_client, market_data_service) -> None:
    market_data_service.bars_error = MarketDataRangeTooLargeError()
    response = api_client.get(
        "/api/v1/market-data/bars",
        params={
            "ticker": "AAPL",
            "timespan": "minute",
            "from": "2026-02-09",
            "to": "2026-02-10",
        },
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "MARKET_DATA_RANGE_TOO_LARGE"


def test_bars_success_sets_contract_headers(api_client, market_data_service) -> None:
    response = api_client.get(
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
    assert response.headers["X-Data-Source"] in {"REST", "DB", "DB_AGG", "DB_AGG_MIXED"}
    assert response.headers["X-Partial-Range"] in {"true", "false"}
    assert market_data_service.list_bars_calls[0]["ticker"] == "AAPL"
