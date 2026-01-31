from __future__ import annotations

import httpx


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = "https://api.polygon.io") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        params["apiKey"] = self.api_key
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

