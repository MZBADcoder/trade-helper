from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from typing import Any

try:
    from massive import RESTClient as SDKRestClient
except ImportError:
    try:
        from polygon import RESTClient as SDKRestClient  # type: ignore[no-redef]
    except ImportError:
        SDKRestClient = None  # type: ignore[assignment]


class MassiveClient:
    def __init__(self, api_key: str, base_url: str = "https://api.massive.com") -> None:
        _ = base_url
        if not api_key:
            raise ValueError("Massive API key is not configured")

        self.api_key = api_key
        if SDKRestClient is None:
            raise RuntimeError(
                "Massive SDK is not installed. Add dependency 'massive' (legacy package name 'polygon' also works)."
            )
        self._client = SDKRestClient(api_key)

    async def list_aggs(
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
    ) -> list[Any]:
        return await asyncio.to_thread(
            self._list_aggs_sync,
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_date=from_date,
            to_date=to_date,
            adjusted=adjusted,
            sort=sort,
            limit=limit,
        )

    async def list_snapshots(self, *, tickers: list[str]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_snapshots_sync, tickers=tickers)

    async def list_market_holidays(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_market_holidays_sync)

    async def get_market_status(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_market_status_sync)

    def _list_aggs_sync(
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
    ) -> list[Any]:
        raw = self._client.list_aggs(
            ticker,
            multiplier,
            timespan,
            from_date,
            to_date,
            adjusted=adjusted,
            sort=sort,
            limit=limit,
        )
        return _materialize_result(raw)

    def _list_snapshots_sync(self, *, tickers: list[str]) -> list[dict[str, Any]]:
        joined = ",".join(tickers)
        candidates = (
            ("get_snapshot_all", {"market_type": "stocks", "tickers": joined}),
            ("list_snapshots", {"tickers": joined}),
            ("list_ticker_snapshots", {"tickers": joined}),
        )
        raw = self._call_first_supported(candidates)
        return self._normalize_result_list(raw)

    def _list_market_holidays_sync(self) -> list[dict[str, Any]]:
        candidates = (("get_market_holidays", {}),)
        raw = self._call_first_supported(candidates)
        return self._normalize_result_list(raw)

    def _get_market_status_sync(self) -> dict[str, Any]:
        candidates = (("get_market_status", {}),)
        raw = self._call_first_supported(candidates)
        normalized = _to_dict(raw)
        return normalized if normalized is not None else {}

    def _call_first_supported(
        self,
        candidates: Iterable[tuple[str, dict[str, Any]]],
    ) -> Any:
        for method_name, kwargs in candidates:
            method = getattr(self._client, method_name, None)
            if method is None:
                continue
            try:
                return method(**kwargs)
            except TypeError:
                continue
        raise RuntimeError("Massive SDK does not provide the requested method")

    @staticmethod
    def _normalize_result_list(raw: Any) -> list[dict[str, Any]]:
        if raw is None:
            return []
        if isinstance(raw, dict):
            if isinstance(raw.get("results"), list):
                return [item_dict for item in raw["results"] if (item_dict := _to_dict(item)) is not None]
            if isinstance(raw.get("tickers"), list):
                return [item_dict for item in raw["tickers"] if (item_dict := _to_dict(item)) is not None]
            normalized = _to_dict(raw)
            return [normalized] if normalized is not None else []
        if isinstance(raw, list):
            return [item_dict for item in raw if (item_dict := _to_dict(item)) is not None]
        if isinstance(raw, Iterable):
            return [item_dict for item in raw if (item_dict := _to_dict(item)) is not None]
        return []


def _materialize_result(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        return list(raw)
    return [raw]


def _to_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, Mapping):
        return dict(raw)
    if hasattr(raw, "__dict__"):
        return vars(raw)
    return None
