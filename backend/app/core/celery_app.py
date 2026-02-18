from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "trader_helper",
    broker=settings.redis_url,
    include=["app.tasks.market_data", "app.tasks.scan"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scan-iv-every-15-minutes": {
            "task": "app.tasks.scan.scan_iv",
            "schedule": 15 * 60,
        },
        "aggregate-minute-bars-5m-every-minute": {
            "task": "app.tasks.market_data.aggregate_minute_bars_5m",
            "schedule": 60,
        },
        "aggregate-minute-bars-15m-every-minute": {
            "task": "app.tasks.market_data.aggregate_minute_bars_15m",
            "schedule": 60,
        },
        "aggregate-minute-bars-60m-every-minute": {
            "task": "app.tasks.market_data.aggregate_minute_bars_60m",
            "schedule": 60,
        },
        "prune-minute-bars-retention-hourly": {
            "task": "app.tasks.market_data.prune_minute_bars_retention",
            "schedule": 60 * 60,
        },
    },
)
