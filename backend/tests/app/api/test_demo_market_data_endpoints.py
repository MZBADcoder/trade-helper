from __future__ import annotations


def test_demo_watchlist_returns_single_amd(api_client) -> None:
    response = api_client.get("/api/v1/demo/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [{"ticker": "AMD", "created_at": None}]


def test_demo_bars_returns_replay_window_and_headers(api_client) -> None:
    response = api_client.get(
        "/api/v1/demo/market-data/bars",
        params={
            "ticker": "AMD",
            "timespan": "minute",
            "multiplier": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 30
    assert payload[0]["ticker"] == "AMD"
    assert payload[0]["timespan"] == "minute"
    assert response.headers["X-Data-Source"] == "DEMO_MOCK"
    assert response.headers["X-Partial-Range"] == "false"


def test_demo_bars_reject_non_amd_symbol(api_client) -> None:
    response = api_client.get(
        "/api/v1/demo/market-data/bars",
        params={
            "ticker": "AAPL",
            "timespan": "minute",
            "multiplier": 1,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "DEMO_MARKET_DATA_INVALID_REQUEST"


def test_demo_snapshots_returns_single_item(api_client) -> None:
    response = api_client.get(
        "/api/v1/demo/market-data/snapshots",
        params={"tickers": "AMD"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["ticker"] == "AMD"
    assert payload["items"][0]["source"] == "DEMO_MOCK"


def test_demo_snapshots_reject_non_amd_symbol(api_client) -> None:
    response = api_client.get(
        "/api/v1/demo/market-data/snapshots",
        params={"tickers": "AAPL"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "DEMO_MARKET_DATA_INVALID_REQUEST"
