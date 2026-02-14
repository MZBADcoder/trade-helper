from __future__ import annotations

from app.infrastructure.clients.massive import MassiveClient


def _build_client_with_stub(stub_client: object) -> MassiveClient:
    client = MassiveClient.__new__(MassiveClient)
    client.api_key = "test"
    client._client = stub_client
    return client


def test_list_options_chain_uses_sdk_strike_filter_kwargs() -> None:
    calls: list[dict] = []

    class StubSdkClient:
        def list_options_contracts(
            self,
            *,
            underlying_ticker: str | None = None,
            expiration_date: str | None = None,
            strike_price_gte: float | None = None,
            strike_price_lte: float | None = None,
            contract_type: str | None = None,
            limit: int | None = None,
            cursor: str | None = None,
        ):
            calls.append(
                {
                    "underlying_ticker": underlying_ticker,
                    "expiration_date": expiration_date,
                    "strike_price_gte": strike_price_gte,
                    "strike_price_lte": strike_price_lte,
                    "contract_type": contract_type,
                    "limit": limit,
                    "cursor": cursor,
                }
            )
            return {"results": [{"option_ticker": "O:AAPL260221C00210000"}], "next_url": None}

    client = _build_client_with_stub(StubSdkClient())

    result = client.list_options_chain(
        underlying="AAPL",
        expiration="2026-02-21",
        strike_from=200,
        strike_to=220,
        option_type="call",
        limit=200,
        cursor="eyJvZmZzZXQiOjIwMH0=",
    )

    assert result["results"][0]["option_ticker"] == "O:AAPL260221C00210000"
    assert calls == [
        {
            "underlying_ticker": "AAPL",
            "expiration_date": "2026-02-21",
            "strike_price_gte": 200,
            "strike_price_lte": 220,
            "contract_type": "call",
            "limit": 200,
            "cursor": "eyJvZmZzZXQiOjIwMH0=",
        }
    ]


def test_get_options_contract_uses_massive_sdk_signature() -> None:
    calls: list[str] = []

    class StubSdkClient:
        def get_options_contract(self, ticker: str):  # pragma: no cover - signature validation target
            calls.append(ticker)
            return {"results": {"underlying": "AAPL", "expiration": "2026-02-21"}}

    client = _build_client_with_stub(StubSdkClient())

    result = client.get_options_contract(
        option_ticker="O:AAPL260221C00210000",
        include_greeks=True,
    )

    assert calls == ["O:AAPL260221C00210000"]
    assert result["results"]["underlying"] == "AAPL"


def test_get_options_contract_falls_back_to_snapshot_signature() -> None:
    calls: list[tuple[str, str]] = []

    class StubSdkClient:
        def get_snapshot_option(self, underlying_asset: str, option_contract: str):
            calls.append((underlying_asset, option_contract))
            return {"results": {"underlying": underlying_asset, "option_ticker": option_contract}}

    client = _build_client_with_stub(StubSdkClient())

    result = client.get_options_contract(
        option_ticker="O:MSFT260221P00300000",
        include_greeks=False,
    )

    assert calls == [("MSFT", "O:MSFT260221P00300000")]
    assert result["results"]["underlying"] == "MSFT"
