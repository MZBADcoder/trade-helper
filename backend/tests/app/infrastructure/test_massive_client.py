from __future__ import annotations

from app.infrastructure.clients.massive import MassiveClient


def _build_client_with_stub(stub_client: object) -> MassiveClient:
    client = MassiveClient.__new__(MassiveClient)
    client.api_key = "test"
    client._client = stub_client
    return client


async def test_list_snapshots_uses_sdk_method() -> None:
    class StubSdkClient:
        def list_snapshots(self, tickers: str):
            assert tickers == "AAPL,NVDA"
            return {
                "results": [
                    {"ticker": "AAPL", "last_trade": {"price": 201.2}},
                    {"ticker": "NVDA", "last_trade": {"price": 810.5}},
                ]
            }

    client = _build_client_with_stub(StubSdkClient())

    result = await client.list_snapshots(tickers=["AAPL", "NVDA"])

    assert result[0]["ticker"] == "AAPL"
    assert result[1]["ticker"] == "NVDA"


async def test_list_market_holidays_uses_sdk_method() -> None:
    class StubSdkClient:
        def get_market_holidays(self):
            return [
                {
                    "date": "2026-07-03",
                    "status": "closed",
                    "open": "",
                    "close": "",
                }
            ]

    client = _build_client_with_stub(StubSdkClient())

    result = await client.list_market_holidays()

    assert result == [{"date": "2026-07-03", "status": "closed", "open": "", "close": ""}]


async def test_get_market_status_uses_sdk_method() -> None:
    class StubSdkClient:
        def get_market_status(self):
            return {"market": "open"}

    client = _build_client_with_stub(StubSdkClient())

    result = await client.get_market_status()

    assert result == {"market": "open"}
