from __future__ import annotations

from app.application.container import build_market_data_service
from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_5m")
def aggregate_minute_bars_5m() -> dict[str, int]:
    service = build_market_data_service()
    produced = service.precompute_minute_aggregates(
        multiplier=5,
        lookback_trade_days=settings.market_data_minute_retention_trade_days,
    )
    return {"multiplier": 5, "produced": produced}


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_15m")
def aggregate_minute_bars_15m() -> dict[str, int]:
    service = build_market_data_service()
    produced = service.precompute_minute_aggregates(
        multiplier=15,
        lookback_trade_days=settings.market_data_minute_retention_trade_days,
    )
    return {"multiplier": 15, "produced": produced}


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_60m")
def aggregate_minute_bars_60m() -> dict[str, int]:
    service = build_market_data_service()
    produced = service.precompute_minute_aggregates(
        multiplier=60,
        lookback_trade_days=settings.market_data_minute_retention_trade_days,
    )
    return {"multiplier": 60, "produced": produced}


@celery_app.task(name="app.tasks.market_data.prune_minute_bars_retention")
def prune_minute_bars_retention() -> dict[str, int]:
    service = build_market_data_service()
    return service.enforce_minute_retention(
        keep_trade_days=settings.market_data_minute_retention_trade_days,
    )
