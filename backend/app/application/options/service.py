from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from app.domain.options.schemas import OptionChainResult, OptionContract, OptionExpirationsResult
from app.domain.options.schemas import OptionChainItem, OptionExpiration, OptionGreeks, OptionQuote, OptionSession
from app.infrastructure.clients.massive import MassiveClient

_UNDERLYING_PATTERN = re.compile(r"^[A-Z.]{1,15}$")
_OPTION_TYPES = {"call", "put", "all"}
_EXPIRATION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DefaultOptionsApplicationService:
    def __init__(self, *, massive_client: MassiveClient | None = None) -> None:
        self._massive_client = massive_client

    def list_expirations(
        self,
        *,
        underlying: str,
        limit: int = 12,
        include_expired: bool = False,
    ) -> OptionExpirationsResult:
        normalized = _normalize_underlying(underlying)
        if limit < 1 or limit > 36:
            raise ValueError("OPTIONS_INVALID_LIMIT")
        if self._massive_client is None:
            raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")

        try:
            contracts = self._massive_client.list_options_expirations(
                underlying=normalized,
                limit=limit,
                include_expired=include_expired,
            )
        except Exception as exc:
            raise ValueError(_map_options_upstream_error(exc, not_found_code="OPTIONS_UNDERLYING_NOT_FOUND")) from exc

        expirations = _contracts_to_expirations(contracts=contracts, include_expired=include_expired)
        if not expirations:
            raise ValueError("OPTIONS_UNDERLYING_NOT_FOUND")

        return OptionExpirationsResult(
            underlying=normalized,
            expirations=expirations[:limit],
            source="REST",
            updated_at=datetime.now(tz=timezone.utc),
        )

    def list_chain(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None = None,
        strike_to: float | None = None,
        option_type: str = "all",
        limit: int = 200,
        cursor: str | None = None,
    ) -> OptionChainResult:
        normalized_underlying = _normalize_underlying(underlying)
        _parse_expiration(expiration)
        if strike_from is not None and strike_to is not None and strike_from > strike_to:
            raise ValueError("OPTIONS_INVALID_STRIKE_RANGE")

        normalized_option_type = option_type.strip().lower()
        if normalized_option_type not in _OPTION_TYPES:
            raise ValueError("OPTIONS_INVALID_OPTION_TYPE")
        if limit < 1 or limit > 500:
            raise ValueError("OPTIONS_INVALID_LIMIT")
        if self._massive_client is None:
            raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")

        try:
            payload = self._massive_client.list_options_chain(
                underlying=normalized_underlying,
                expiration=expiration,
                strike_from=strike_from,
                strike_to=strike_to,
                option_type=normalized_option_type,
                limit=limit,
                cursor=cursor,
            )
        except Exception as exc:
            raise ValueError(_map_options_upstream_error(exc, not_found_code="OPTIONS_CHAIN_NOT_FOUND")) from exc

        raw_items = payload.get("results", [])
        items = [_to_chain_item(raw) for raw in raw_items]
        items = [item for item in items if item is not None]
        if not items:
            raise ValueError("OPTIONS_CHAIN_NOT_FOUND")

        return OptionChainResult(
            underlying=normalized_underlying,
            expiration=expiration,
            items=items,
            next_cursor=_extract_next_cursor(payload),
        )

    def get_contract(
        self,
        *,
        option_ticker: str,
        include_greeks: bool = True,
    ) -> OptionContract:
        normalized_ticker = option_ticker.strip().upper()
        if not normalized_ticker.startswith("O:"):
            raise ValueError("OPTIONS_INVALID_TICKER")
        if self._massive_client is None:
            raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")

        try:
            payload = self._massive_client.get_options_contract(
                option_ticker=normalized_ticker,
                include_greeks=include_greeks,
            )
        except Exception as exc:
            raise ValueError(_map_options_upstream_error(exc, not_found_code="OPTIONS_CONTRACT_NOT_FOUND")) from exc

        contract = _to_option_contract(
            option_ticker=normalized_ticker,
            payload=payload,
            include_greeks=include_greeks,
        )
        if contract is None:
            raise ValueError("OPTIONS_CONTRACT_NOT_FOUND")
        return contract


def _normalize_underlying(underlying: str) -> str:
    symbol = underlying.strip().upper()
    if not symbol or not _UNDERLYING_PATTERN.fullmatch(symbol):
        raise ValueError("OPTIONS_INVALID_UNDERLYING")
    return symbol


def _parse_expiration(expiration: str) -> date:
    if not _EXPIRATION_PATTERN.fullmatch(expiration.strip()):
        raise ValueError("OPTIONS_INVALID_EXPIRATION")
    try:
        return date.fromisoformat(expiration)
    except ValueError as exc:
        raise ValueError("OPTIONS_INVALID_EXPIRATION") from exc


def _map_options_upstream_error(exc: Exception, *, not_found_code: str) -> str:
    detail = str(exc).strip()
    if detail in {
        "OPTIONS_UPSTREAM_UNAVAILABLE",
        "OPTIONS_INVALID_CURSOR",
        "OPTIONS_INVALID_TICKER",
        "OPTIONS_UNDERLYING_NOT_FOUND",
        "OPTIONS_CHAIN_NOT_FOUND",
        "OPTIONS_CONTRACT_NOT_FOUND",
    }:
        return detail

    lowered = detail.lower()
    if "not found" in lowered or "404" in lowered:
        return not_found_code
    if "cursor" in lowered and ("invalid" in lowered or "malformed" in lowered):
        return "OPTIONS_INVALID_CURSOR"
    return "OPTIONS_UPSTREAM_UNAVAILABLE"


def _contracts_to_expirations(
    *,
    contracts: list[dict[str, Any]],
    include_expired: bool,
) -> list[OptionExpiration]:
    today = date.today()
    counter: Counter[date] = Counter()
    for contract in contracts:
        expiry_raw = contract.get("expiration_date") or contract.get("expiration")
        if expiry_raw is None:
            continue
        try:
            expiry_date = date.fromisoformat(str(expiry_raw))
        except ValueError:
            continue
        if not include_expired and expiry_date < today:
            continue
        counter[expiry_date] += 1

    expirations: list[OptionExpiration] = []
    for expiry_date in sorted(counter.keys()):
        expirations.append(
            OptionExpiration(
                date=expiry_date.isoformat(),
                days_to_expiration=(expiry_date - today).days,
                contract_count=counter[expiry_date],
            )
        )
    return expirations


def _to_chain_item(raw: object) -> OptionChainItem | None:
    ticker = _extract_str(raw, "option_ticker", "ticker")
    if not ticker:
        return None

    return OptionChainItem(
        option_ticker=ticker.upper(),
        option_type=(_extract_str(raw, "option_type", "contract_type") or "call").lower(),
        strike=_extract_float(raw, "strike", "strike_price"),
        bid=_extract_float(raw, "bid"),
        ask=_extract_float(raw, "ask"),
        last=_extract_float(raw, "last"),
        iv=_extract_float(raw, "iv", "implied_volatility"),
        volume=int(_extract_float(raw, "volume")),
        open_interest=int(_extract_float(raw, "open_interest")),
        updated_at=_extract_datetime(raw, "updated_at", "as_of") or datetime.now(tz=timezone.utc),
        source=(_extract_str(raw, "source") or "REST").upper(),
    )


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    direct = payload.get("next_cursor")
    if isinstance(direct, str) and direct.strip():
        return direct

    next_url = payload.get("next_url")
    if not isinstance(next_url, str) or "cursor=" not in next_url:
        return None
    return next_url.split("cursor=", maxsplit=1)[-1].strip() or None


def _to_option_contract(
    *,
    option_ticker: str,
    payload: dict[str, Any],
    include_greeks: bool,
) -> OptionContract | None:
    results = payload.get("results")
    raw: object = payload
    if isinstance(results, list) and results:
        raw = results[0]
    elif isinstance(results, dict):
        raw = results

    underlying = _extract_str(raw, "underlying", "underlying_ticker")
    expiration = _extract_str(raw, "expiration", "expiration_date")
    if not underlying or not expiration:
        return None

    greeks_value: OptionGreeks | None = None
    if include_greeks:
        greeks_value = _to_greeks(_extract_value(raw, "greeks"))

    quote_raw = _extract_value(raw, "quote")
    session_raw = _extract_value(raw, "session")
    return OptionContract(
        option_ticker=option_ticker,
        underlying=underlying.upper(),
        expiration=expiration,
        option_type=(_extract_str(raw, "option_type", "contract_type") or "call").lower(),
        strike=_extract_float(raw, "strike", "strike_price"),
        multiplier=int(_extract_float(raw, "multiplier")) or 100,
        quote=OptionQuote(
            bid=_extract_float(quote_raw or raw, "bid"),
            ask=_extract_float(quote_raw or raw, "ask"),
            last=_extract_float(quote_raw or raw, "last"),
            updated_at=_extract_datetime(quote_raw or raw, "updated_at", "as_of")
            or datetime.now(tz=timezone.utc),
        ),
        session=OptionSession(
            open=_extract_float(session_raw or raw, "open"),
            high=_extract_float(session_raw or raw, "high"),
            low=_extract_float(session_raw or raw, "low"),
            volume=int(_extract_float(session_raw or raw, "volume")),
            open_interest=int(_extract_float(session_raw or raw, "open_interest")),
        ),
        greeks=greeks_value,
        source=(_extract_str(raw, "source") or "REST").upper(),
    )


def _to_greeks(raw: object | None) -> OptionGreeks | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return OptionGreeks(
        delta=_extract_float(raw, "delta"),
        gamma=_extract_float(raw, "gamma"),
        theta=_extract_float(raw, "theta"),
        vega=_extract_float(raw, "vega"),
        iv=_extract_float(raw, "iv", "implied_volatility"),
    )


def _extract_value(raw: object, key: str) -> object | None:
    if isinstance(raw, dict):
        return raw.get(key)
    if hasattr(raw, key):
        return getattr(raw, key)
    return None


def _extract_str(raw: object, *keys: str) -> str:
    for key in keys:
        value = _extract_value(raw, key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_float(raw: object, *keys: str) -> float:
    for key in keys:
        value = _extract_value(raw, key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _extract_datetime(raw: object, *keys: str) -> datetime | None:
    value: object | None = None
    for key in keys:
        value = _extract_value(raw, key)
        if value is not None:
            break
    if value is None:
        return None
    return _to_utc_datetime(value)


def _to_utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None
