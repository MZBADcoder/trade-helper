from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import install_api_error_handlers
from app.api.v1.router import api_router


def test_demo_stream_pushes_status_and_market_messages() -> None:
    app = FastAPI()
    install_api_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/demo/market-data/stream") as websocket:
            status_payload = websocket.receive_json()
            assert status_payload["type"] == "system.status"
            assert status_payload["data"]["latency"] == "real-time"

            market_messages = [websocket.receive_json() for _ in range(3)]
            assert [item["type"] for item in market_messages] == [
                "market.quote",
                "market.trade",
                "market.aggregate",
            ]
            for item in market_messages:
                assert item["data"]["symbol"] == "AMD"
                assert isinstance(item["data"]["replay_index"], int)
