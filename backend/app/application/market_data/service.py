from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from app.core.config import settings
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.infrastructure.clients.massive import MassiveClient
from app.infrastructure.clients.massive_mapper import map_massive_aggregates_to_market_bars
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")


class MarketDataApplicationService:
    def __init__(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        massive_client: MassiveClient | None = None,
    ) -> None:
        self._uow = uow
        self._massive_client = massive_client

    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = self._default_start_date(timespan=timespan, end_date=end_date)

        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        normalized_timespan = timespan.strip().lower()
        if not normalized_timespan:
            raise ValueError("Timespan is required")
        if multiplier < 1:
            raise ValueError("Multiplier must be >= 1")
        if end_date < start_date:
            raise ValueError("End date must be on or after start date")

        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            coverage = repo.get_range_coverage(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
            )
            if coverage and coverage[0] <= start_dt and coverage[1] >= end_dt:
                return repo.list_bars(
                    ticker=normalized,
                    timespan=normalized_timespan,
                    multiplier=multiplier,
                    start_at=start_dt,
                    end_at=end_dt,
                    limit=limit,
                )

            if self._massive_client is None:
                raise ValueError("Massive client not configured")

            bars = self._fetch_from_massive(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
                start_date=start_date,
                end_date=end_date,
            )
            if bars:
                repo.upsert_bars(bars)
                uow.commit()

            return repo.list_bars(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
                start_at=start_dt,
                end_at=end_dt,
                limit=limit,
            )

    def prefetch_default(self, *, ticker: str) -> None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")

        today = date.today()
        daily_start = today - timedelta(days=settings.market_data_daily_lookback_days)
        intraday_start = today - timedelta(days=settings.market_data_intraday_lookback_days)

        self.list_bars(
            ticker=normalized,
            timespan="day",
            multiplier=1,
            start_date=daily_start,
            end_date=today,
        )
        self.list_bars(
            ticker=normalized,
            timespan="minute",
            multiplier=1,
            start_date=intraday_start,
            end_date=today,
        )

    def list_snapshots(self, *, tickers: list[str]) -> list[MarketSnapshot]:
        normalized_tickers = _normalize_tickers(tickers=tickers)
        if self._massive_client is None:
            raise ValueError("MARKET_DATA_UPSTREAM_UNAVAILABLE")

        try:
            payload = self._massive_client.list_snapshots(tickers=normalized_tickers)
        except Exception as exc:
            raise ValueError(_map_market_data_upstream_error(exc)) from exc

        snapshots: list[MarketSnapshot] = []
        for item in payload:
            mapped = _to_market_snapshot(item)
            if mapped is not None:
                snapshots.append(mapped)
        return snapshots

    @staticmethod
    def _default_start_date(*, timespan: str, end_date: date) -> date:
        if timespan.strip().lower() == "minute":
            return end_date - timedelta(days=settings.market_data_intraday_lookback_days)
        return end_date - timedelta(days=settings.market_data_daily_lookback_days)

    def _fetch_from_massive(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
    ) -> list[MarketBar]:
        aggregates = self._massive_client.list_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_date=start_date.isoformat(),
            to_date=end_date.isoformat(),
            adjusted=True,
            sort="asc",
            limit=50000,
        )
        return map_massive_aggregates_to_market_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            aggregates=aggregates,
        )


def _require_market_data_repo(uow: SqlAlchemyUnitOfWork):
    if uow.market_data_repo is None:
        raise RuntimeError("Market data repository not configured")
    return uow.market_data_repo


def _normalize_tickers(*, tickers: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if not _TICKER_PATTERN.fullmatch(symbol):
            raise ValueError("MARKET_DATA_INVALID_TICKERS")
        if symbol not in seen:
            seen.add(symbol)
            unique.append(symbol)

    if not unique or len(unique) > 50:
        raise ValueError("MARKET_DATA_INVALID_TICKERS")
    return unique


def _map_market_data_upstream_error(exc: Exception) -> str:
    detail = str(exc).strip()
    if detail in {"MARKET_DATA_RATE_LIMITED", "MARKET_DATA_UPSTREAM_UNAVAILABLE"}:
        return detail

    lowered = detail.lower()
    if "rate limit" in lowered or "429" in lowered:
        return "MARKET_DATA_RATE_LIMITED"
    return "MARKET_DATA_UPSTREAM_UNAVAILABLE"


def _to_market_snapshot(raw: object) -> MarketSnapshot | None:
    ticker = _extract_str(raw, "ticker", "symbol")
    if not ticker:
        return None

    updated_at = _extract_datetime(raw, "updated_at", "updated", "timestamp", "t")
    if updated_at is None:
        updated_at = datetime.now(tz=timezone.utc)

    return MarketSnapshot(
        ticker=ticker.upper(),
        last=_extract_float(raw, "last", "price", "last_trade.price"),
        change=_extract_float(raw, "change", "todays_change"),
        change_pct=_extract_float(raw, "change_pct", "todays_change_perc", "todays_change_percent"),
        open=_extract_float(raw, "open", "day.open"),
        high=_extract_float(raw, "high", "day.high"),
        low=_extract_float(raw, "low", "day.low"),
        volume=int(_extract_float(raw, "volume", "day.volume")),
        updated_at=updated_at,
        market_status=_extract_str(raw, "market_status") or "unknown",
        source=(_extract_str(raw, "source") or "REST").upper(),
    )


def _extract_value(raw: object, key: str) -> object | None:
    parts = key.split(".")
    current: object | None = raw
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if hasattr(current, part):
            current = getattr(current, part)
            continue
        return None
    return current


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

    if isinstance(value, (int, float)):
        numeric = float(value)
        abs_value = abs(numeric)
        if abs_value >= 10_000_000_000_000:
            numeric = numeric / 1_000_000_000.0
        elif abs_value >= 10_000_000_000:
            numeric = numeric / 1_000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)

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
