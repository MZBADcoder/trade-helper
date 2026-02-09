from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:
    from massive import RESTClient as SDKRestClient
except ImportError:
    try:
        from polygon import RESTClient as SDKRestClient  # type: ignore[no-redef]
    except ImportError:
        SDKRestClient = None  # type: ignore[assignment]


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = "https://api.massive.com") -> None:
        _ = base_url
        if not api_key:
            raise ValueError("Polygon API key is not configured")

        self.api_key = api_key
        if SDKRestClient is None:
            raise RuntimeError(
                "Polygon SDK is not installed. Add dependency 'massive' (or compatible 'polygon')."
            )
        self._client = SDKRestClient(api_key)

    def list_aggs(
        self,
        *,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50000,
    ) -> Iterable[Any]:
        return self._client.list_aggs(
            ticker,
            multiplier,
            timespan,
            from_date,
            to_date,
            adjusted=adjusted,
            sort=sort,
            limit=limit,
        )
