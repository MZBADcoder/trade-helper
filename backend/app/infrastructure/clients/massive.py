from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
import re
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

    async def list_options_expirations(
        self,
        *,
        underlying: str,
        limit: int,
        include_expired: bool,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._list_options_expirations_sync,
            underlying=underlying,
            limit=limit,
            include_expired=include_expired,
        )

    async def list_options_chain(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None,
        strike_to: float | None,
        option_type: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._list_options_chain_sync,
            underlying=underlying,
            expiration=expiration,
            strike_from=strike_from,
            strike_to=strike_to,
            option_type=option_type,
            limit=limit,
            cursor=cursor,
        )

    async def get_options_contract(
        self,
        *,
        option_ticker: str,
        include_greeks: bool,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._get_options_contract_sync,
            option_ticker=option_ticker,
            include_greeks=include_greeks,
        )

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

    def _list_options_expirations_sync(
        self,
        *,
        underlying: str,
        limit: int,
        include_expired: bool,
    ) -> list[dict[str, Any]]:
        candidates = (
            (
                "list_options_contracts",
                {
                    "underlying_ticker": underlying,
                    "expired": str(include_expired).lower(),
                    "limit": limit,
                },
            ),
            (
                "list_options_contracts",
                {
                    "underlying_ticker": underlying,
                    "expired": include_expired,
                    "limit": limit,
                },
            ),
        )
        raw = self._call_first_supported(candidates)
        return self._normalize_result_list(raw)

    def _list_options_chain_sync(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None,
        strike_to: float | None,
        option_type: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "underlying_ticker": underlying,
            "expiration_date": expiration,
            "limit": limit,
        }
        if strike_from is not None:
            payload["strike_price_gte"] = strike_from
        if strike_to is not None:
            payload["strike_price_lte"] = strike_to
        if option_type in {"call", "put"}:
            payload["contract_type"] = option_type
        candidates: list[tuple[str, dict[str, Any]]] = []
        if cursor:
            candidates.append(
                (
                    "list_options_contracts",
                    {
                        **payload,
                        "params": {
                            "cursor": cursor,
                        },
                    },
                )
            )
            candidates.append(
                (
                    "list_options_contracts",
                    {
                        **payload,
                        "cursor": cursor,
                    },
                )
            )
        else:
            candidates.append(("list_options_contracts", payload))

        raw = self._call_first_supported(candidates)
        if isinstance(raw, dict):
            return raw
        return {"results": self._normalize_result_list(raw), "next_url": None}

    def _get_options_contract_sync(
        self,
        *,
        option_ticker: str,
        include_greeks: bool,
    ) -> dict[str, Any]:
        _ = include_greeks
        underlying = _extract_underlying_from_option_ticker(option_ticker)
        candidates = (
            ("get_options_contract", {"ticker": option_ticker}),
            ("get_option_contract", {"option_ticker": option_ticker}),
            ("get_snapshot_option", {"underlying_asset": underlying, "option_contract": option_ticker}),
            ("get_snapshot_option", {"ticker": option_ticker}),
        )
        raw = self._call_first_supported(candidates)
        if isinstance(raw, dict):
            return raw
        return {"results": [raw]}

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


_OPTION_TICKER_RE = re.compile(r"^O:([A-Z.]+)")


def _extract_underlying_from_option_ticker(option_ticker: str) -> str:
    normalized = option_ticker.strip().upper()
    matched = _OPTION_TICKER_RE.match(normalized)
    if matched:
        return matched.group(1)
    return normalized
