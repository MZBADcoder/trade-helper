from __future__ import annotations


def test_options_expirations_respects_limit_range(api_client) -> None:
    invalid = api_client.get("/api/v1/options/expirations", params={"underlying": "AAPL", "limit": 37})
    valid = api_client.get("/api/v1/options/expirations", params={"underlying": "AAPL"})

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "OPTIONS_INVALID_LIMIT"
    assert valid.status_code == 200
    assert valid.json()["underlying"] == "AAPL"


def test_options_chain_rejects_invalid_strike_range(api_client) -> None:
    response = api_client.get(
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


def test_options_contract_include_greeks_toggle(api_client) -> None:
    with_greeks = api_client.get("/api/v1/options/contracts/O:AAPL260221C00210000")
    without_greeks = api_client.get(
        "/api/v1/options/contracts/O:AAPL260221C00210000",
        params={"include_greeks": "false"},
    )

    assert with_greeks.status_code == 200
    assert with_greeks.json()["greeks"]["delta"] == 0.45
    assert without_greeks.status_code == 200
    assert without_greeks.json()["greeks"] is None
