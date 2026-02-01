from __future__ import annotations

from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.scan.scan_iv")
def scan_iv() -> dict:
    raise NotImplementedError("scan task not implemented")
