from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "trader_helper",
    broker=settings.redis_url,
    include=["app.tasks.scan"],
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
        }
    },
)

