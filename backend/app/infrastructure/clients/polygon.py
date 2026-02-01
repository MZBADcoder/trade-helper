from __future__ import annotations

import httpx


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = "https://api.polygon.io") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, params: dict | None = None) -> dict:
        if not self.api_key:
            raise ValueError("Polygon API key is not configured")

        url = path if path.startswith("http") else f"{self.base_url}{path}"
        query_params = dict(params or {})
        query_params.setdefault("apiKey", self.api_key)

        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=query_params)
            response.raise_for_status()
            return response.json()
