from __future__ import annotations

import pytest

from app.application.options.service import OptionsApplicationService
from app.domain.options.schemas import OptionChainResult, OptionContract, OptionExpirationsResult


class FakeMassiveOptionsClient:
    def __init__(self) -> None:
        self.expirations_calls: list[dict] = []
        self.chain_calls: list[dict] = []
        self.contract_calls: list[dict] = []

    def list_options_expirations(
        self,
        *,
        underlying: str,
        limit: int,
        include_expired: bool,
    ) -> list[dict]:
        self.expirations_calls.append(
            {
                "underlying": underlying,
                "limit": limit,
                "include_expired": include_expired,
            }
        )
        return [
            {"expiration_date": "2099-02-21"},
            {"expiration_date": "2099-02-21"},
            {"expiration_date": "2099-03-21"},
        ]

    def list_options_chain(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None,
        strike_to: float | None,
        option_type: str,
        limit: int,
        cursor: str | None,
    ) -> dict:
        self.chain_calls.append(
            {
                "underlying": underlying,
                "expiration": expiration,
                "strike_from": strike_from,
                "strike_to": strike_to,
                "option_type": option_type,
                "limit": limit,
                "cursor": cursor,
            }
        )
        return {
            "results": [
                {
                    "option_ticker": "O:AAPL260221C00210000",
                    "option_type": "call",
                    "strike": 210,
                    "bid": 1.23,
                    "ask": 1.28,
                    "last": 1.25,
                    "iv": 0.312,
                    "volume": 1532,
                    "open_interest": 10421,
                    "updated_at": "2026-02-10T14:33:02Z",
                    "source": "REST",
                }
            ],
            "next_url": "https://api.massive.com/v3/snapshot/options/AAPL?cursor=eyJvZmZzZXQiOjIwMH0=",
        }

    def get_options_contract(
        self,
        *,
        option_ticker: str,
        include_greeks: bool,
    ) -> dict:
        self.contract_calls.append(
            {
                "option_ticker": option_ticker,
                "include_greeks": include_greeks,
            }
        )
        greeks_payload = {"delta": 0.45, "gamma": 0.03, "theta": -0.08, "vega": 0.11, "iv": 0.312}
        return {
            "results": {
                "underlying": "AAPL",
                "expiration": "2026-02-21",
                "option_type": "call",
                "strike": 210.0,
                "multiplier": 100,
                "quote": {
                    "bid": 1.23,
                    "ask": 1.28,
                    "last": 1.25,
                    "updated_at": "2026-02-10T14:33:02Z",
                },
                "session": {
                    "open": 1.51,
                    "high": 1.58,
                    "low": 1.11,
                    "volume": 1532,
                    "open_interest": 10421,
                },
                "greeks": greeks_payload if include_greeks else None,
                "source": "REST",
            }
        }


def test_list_expirations_raises_options_upstream_unavailable_without_client() -> None:
    service = OptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.list_expirations(underlying="AAPL")


def test_list_expirations_raises_options_upstream_unavailable_when_disabled() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client, enabled=False)

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.list_expirations(underlying="AAPL")


def test_list_expirations_returns_grouped_result() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    result = service.list_expirations(underlying="aapl", limit=12, include_expired=False)

    assert isinstance(result, OptionExpirationsResult)
    assert result.underlying == "AAPL"
    assert len(result.expirations) == 2
    assert result.expirations[0].date == "2099-02-21"
    assert result.expirations[0].contract_count == 2
    assert result.source == "REST"
    assert client.expirations_calls[0]["underlying"] == "AAPL"


def test_list_expirations_rejects_invalid_limit() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    with pytest.raises(ValueError, match="OPTIONS_INVALID_LIMIT"):
        service.list_expirations(underlying="AAPL", limit=37)


def test_list_chain_raises_options_upstream_unavailable_without_client() -> None:
    service = OptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.list_chain(underlying="AAPL", expiration="2026-02-21")


def test_list_chain_returns_domain_result() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    result = service.list_chain(
        underlying="aapl",
        expiration="2026-02-21",
        strike_from=200,
        strike_to=220,
        option_type="call",
        limit=200,
    )

    assert isinstance(result, OptionChainResult)
    assert result.underlying == "AAPL"
    assert result.expiration == "2026-02-21"
    assert result.next_cursor == "eyJvZmZzZXQiOjIwMH0="
    assert result.items[0].option_ticker == "O:AAPL260221C00210000"
    assert result.items[0].option_type == "call"
    assert client.chain_calls[0]["underlying"] == "AAPL"


def test_list_chain_rejects_invalid_expiration() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    with pytest.raises(ValueError, match="OPTIONS_INVALID_EXPIRATION"):
        service.list_chain(underlying="AAPL", expiration="20260221")


def test_get_contract_raises_options_upstream_unavailable_without_client() -> None:
    service = OptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.get_contract(option_ticker="O:AAPL260221C00210000")


def test_get_contract_returns_domain_result_with_greeks() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    result = service.get_contract(option_ticker="o:aapl260221c00210000")

    assert isinstance(result, OptionContract)
    assert result.option_ticker == "O:AAPL260221C00210000"
    assert result.underlying == "AAPL"
    assert result.quote.bid == pytest.approx(1.23)
    assert result.greeks is not None
    assert result.greeks.delta == pytest.approx(0.45)
    assert client.contract_calls[0]["option_ticker"] == "O:AAPL260221C00210000"
    assert client.contract_calls[0]["include_greeks"] is True


def test_get_contract_omits_greeks_when_disabled() -> None:
    client = FakeMassiveOptionsClient()
    service = OptionsApplicationService(massive_client=client)

    result = service.get_contract(
        option_ticker="O:AAPL260221C00210000",
        include_greeks=False,
    )

    assert result.greeks is None
