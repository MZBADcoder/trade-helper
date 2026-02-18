from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import date, datetime, time, timedelta, timezone

from app.core.config import settings
from app.domain.market_data.aggregation import (
    aggregate_bucket,
    aggregate_minute_bars,
    market_trade_date,
    resolve_current_open_bucket,
)
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.infrastructure.clients.massive import MassiveClient
from app.infrastructure.clients.massive_mapper import map_massive_aggregates_to_market_bars
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")
_SUPPORTED_MINUTE_AGG_MULTIPLIERS = {5, 15, 60}


@dataclass(slots=True)
class MarketBarsQueryResult:
    bars: list[MarketBar]
    data_source: str
    partial_range: bool = False


@dataclass(slots=True)
class _BarsQuery:
    ticker: str
    timespan: str
    multiplier: int
    start_date: date
    end_date: date
    start_at: datetime
    end_at: datetime
    limit: int | None


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
        result = self.list_bars_with_meta(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return result.bars

    def list_bars_with_meta(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> MarketBarsQueryResult:
        query = _build_bars_query(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        if query.timespan == "day" and query.multiplier == 1:
            return self._list_day_baseline(query=query)
        if query.timespan == "minute" and query.multiplier == 1:
            return self._list_minute_baseline(query=query)
        if query.timespan == "minute" and query.multiplier in _SUPPORTED_MINUTE_AGG_MULTIPLIERS:
            return self._list_minute_aggregated(query=query)
        return self._list_direct_fallback(query=query)

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

    def precompute_minute_aggregates(
        self,
        *,
        multiplier: int,
        lookback_trade_days: int = 10,
        now: datetime | None = None,
    ) -> int:
        if multiplier not in _SUPPORTED_MINUTE_AGG_MULTIPLIERS:
            raise ValueError("Unsupported minute aggregation multiplier")
        if lookback_trade_days < 1:
            raise ValueError("lookback_trade_days must be >= 1")

        now = now or datetime.now(tz=timezone.utc)
        end_at = now
        keep_from_trade_date = market_trade_date(point=now) - timedelta(days=lookback_trade_days - 1)
        start_at = datetime.combine(keep_from_trade_date, time.min, tzinfo=timezone.utc)

        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            tickers = repo.list_minute_tickers(start_at=start_at, end_at=end_at)

            produced = 0
            for ticker in tickers:
                minute_bars = repo.list_minute_bars(
                    ticker=ticker,
                    start_at=start_at,
                    end_at=end_at,
                    limit=None,
                )
                aggregated = aggregate_minute_bars(
                    ticker=ticker,
                    multiplier=multiplier,
                    bars=minute_bars,
                    source="DB_AGG",
                    now=now,
                    include_unfinished=False,
                )
                if not aggregated:
                    continue
                repo.upsert_minute_agg_bars(aggregated)
                produced += len(aggregated)

            if produced > 0:
                uow.commit()
            return produced

    def enforce_minute_retention(
        self,
        *,
        keep_trade_days: int = 10,
        now: datetime | None = None,
    ) -> dict[str, int]:
        if keep_trade_days < 1:
            raise ValueError("keep_trade_days must be >= 1")

        now = now or datetime.now(tz=timezone.utc)
        keep_from_trade_date = market_trade_date(point=now) - timedelta(days=keep_trade_days - 1)

        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            deleted_minute = repo.delete_minute_bars_before_trade_date(keep_from_trade_date=keep_from_trade_date)
            deleted_agg = repo.delete_minute_agg_before_trade_date(keep_from_trade_date=keep_from_trade_date)
            if deleted_minute > 0 or deleted_agg > 0:
                uow.commit()
            return {
                "minute_deleted": deleted_minute,
                "minute_agg_deleted": deleted_agg,
            }

    @staticmethod
    def _default_start_date(*, timespan: str, end_date: date) -> date:
        if timespan.strip().lower() == "minute":
            return end_date - timedelta(days=settings.market_data_intraday_lookback_days)
        return end_date - timedelta(days=settings.market_data_daily_lookback_days)

    def _list_day_baseline(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            coverage = repo.get_day_range_coverage(ticker=query.ticker)
            if _coverage_contains(coverage=coverage, start_at=query.start_at, end_at=query.end_at):
                return MarketBarsQueryResult(
                    bars=repo.list_day_bars(
                        ticker=query.ticker,
                        start_at=query.start_at,
                        end_at=query.end_at,
                        limit=query.limit,
                    ),
                    data_source="DB",
                    partial_range=False,
                )

            fetched = self._fetch_from_massive(
                ticker=query.ticker,
                timespan="day",
                multiplier=1,
                start_date=query.start_date,
                end_date=query.end_date,
            )
            if fetched:
                repo.upsert_day_bars(fetched)
                uow.commit()

            bars = repo.list_day_bars(
                ticker=query.ticker,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=query.limit,
            )
            return MarketBarsQueryResult(
                bars=bars,
                data_source="REST" if fetched else "DB",
                partial_range=False,
            )

    def _list_minute_baseline(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            coverage = repo.get_minute_range_coverage(ticker=query.ticker)
            if _coverage_contains(coverage=coverage, start_at=query.start_at, end_at=query.end_at):
                return MarketBarsQueryResult(
                    bars=repo.list_minute_bars(
                        ticker=query.ticker,
                        start_at=query.start_at,
                        end_at=query.end_at,
                        limit=query.limit,
                    ),
                    data_source="DB",
                    partial_range=False,
                )

            fetched = self._fetch_from_massive(
                ticker=query.ticker,
                timespan="minute",
                multiplier=1,
                start_date=query.start_date,
                end_date=query.end_date,
            )
            if fetched:
                repo.upsert_minute_bars(fetched)
                uow.commit()

            bars = repo.list_minute_bars(
                ticker=query.ticker,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=query.limit,
            )
            return MarketBarsQueryResult(
                bars=bars,
                data_source="REST" if fetched else "DB",
                partial_range=False,
            )

    def _list_minute_aggregated(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        self._ensure_minute_baseline_coverage(query=query)
        now = datetime.now(tz=timezone.utc)

        with self._uow as uow:
            repo = _require_market_data_repo(uow)

            finalized = repo.list_minute_agg_bars(
                ticker=query.ticker,
                multiplier=query.multiplier,
                start_at=query.start_at,
                end_at=query.end_at,
                final_only=True,
                limit=None,
            )

            mixed_bucket = resolve_current_open_bucket(now=now, multiplier=query.multiplier)
            realtime_item: MarketBar | None = None
            if mixed_bucket is not None:
                bucket_start, bucket_end = mixed_bucket
                if _ranges_intersect(
                    left_start=query.start_at,
                    left_end=query.end_at,
                    right_start=bucket_start,
                    right_end=bucket_end,
                ):
                    realtime_cutoff = min(
                        bucket_end,
                        now + timedelta(microseconds=1),
                        query.end_at + timedelta(microseconds=1),
                    )
                    if realtime_cutoff > bucket_start:
                        minute_items = repo.list_minute_bars_for_bucket(
                            ticker=query.ticker,
                            bucket_start_at=bucket_start,
                            bucket_end_at=realtime_cutoff,
                        )
                        realtime_item = aggregate_bucket(
                            ticker=query.ticker,
                            multiplier=query.multiplier,
                            bars=minute_items,
                            bucket_start=bucket_start,
                            bucket_end=bucket_end,
                            source="DB_AGG_MIXED",
                            is_final=False,
                        )

            merged = _merge_aggregated_bars(
                finalized=finalized,
                realtime_item=realtime_item,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=query.limit,
            )
            if merged:
                return MarketBarsQueryResult(
                    bars=merged,
                    data_source="DB_AGG_MIXED" if realtime_item is not None else "DB_AGG",
                    partial_range=False,
                )

        if settings.market_data_enable_direct_fallback:
            return self._list_direct_fallback(query=query)
        return MarketBarsQueryResult(bars=[], data_source="DB_AGG", partial_range=False)

    def _list_direct_fallback(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        bars = self._fetch_from_massive(
            ticker=query.ticker,
            timespan=query.timespan,
            multiplier=query.multiplier,
            start_date=query.start_date,
            end_date=query.end_date,
        )
        return MarketBarsQueryResult(
            bars=_apply_limit(bars, limit=query.limit),
            data_source="REST",
            partial_range=False,
        )

    def _ensure_minute_baseline_coverage(self, *, query: _BarsQuery) -> None:
        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            coverage = repo.get_minute_range_coverage(ticker=query.ticker)
            if _coverage_contains(coverage=coverage, start_at=query.start_at, end_at=query.end_at):
                return

            fetched = self._fetch_from_massive(
                ticker=query.ticker,
                timespan="minute",
                multiplier=1,
                start_date=query.start_date,
                end_date=query.end_date,
            )
            if not fetched:
                return

            repo.upsert_minute_bars(fetched)
            uow.commit()

    def _fetch_from_massive(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
    ) -> list[MarketBar]:
        if self._massive_client is None:
            raise ValueError("MARKET_DATA_UPSTREAM_UNAVAILABLE")
        try:
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
        except Exception as exc:
            raise ValueError(_map_market_data_upstream_error(exc)) from exc
        return map_massive_aggregates_to_market_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            aggregates=aggregates,
        )


def _build_bars_query(
    *,
    ticker: str,
    timespan: str,
    multiplier: int,
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
) -> _BarsQuery:
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = MarketDataApplicationService._default_start_date(timespan=timespan, end_date=end_date)

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("Ticker is required")

    normalized_timespan = timespan.strip().lower()
    if not normalized_timespan:
        raise ValueError("Timespan is required")

    if multiplier < 1:
        raise ValueError("Multiplier must be >= 1")
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

    start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_at = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    return _BarsQuery(
        ticker=normalized_ticker,
        timespan=normalized_timespan,
        multiplier=multiplier,
        start_date=start_date,
        end_date=end_date,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )


def _require_market_data_repo(uow: SqlAlchemyUnitOfWork):
    if uow.market_data_repo is None:
        raise RuntimeError("Market data repository not configured")
    return uow.market_data_repo


def _coverage_contains(
    *,
    coverage: tuple[datetime, datetime] | None,
    start_at: datetime,
    end_at: datetime,
) -> bool:
    if coverage is None:
        return False
    return coverage[0] <= start_at and coverage[1] >= end_at


def _ranges_intersect(
    *,
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> bool:
    return left_start < right_end and right_start <= left_end


def _merge_aggregated_bars(
    *,
    finalized: list[MarketBar],
    realtime_item: MarketBar | None,
    start_at: datetime,
    end_at: datetime,
    limit: int | None,
) -> list[MarketBar]:
    merged = [bar for bar in finalized if start_at <= bar.start_at <= end_at]
    if realtime_item is not None and start_at <= realtime_item.start_at <= end_at:
        merged = [bar for bar in merged if bar.start_at != realtime_item.start_at]
        merged.append(realtime_item)

    merged.sort(key=lambda bar: bar.start_at)
    return _apply_limit(merged, limit=limit)


def _apply_limit(bars: list[MarketBar], *, limit: int | None) -> list[MarketBar]:
    if not limit or limit < 1:
        return bars
    return bars[:limit]


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
