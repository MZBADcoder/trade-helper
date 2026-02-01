from __future__ import annotations


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = "https://api.polygon.io") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def get(self, path: str, params: dict | None = None) -> dict:
        raise NotImplementedError("polygon client not implemented")
