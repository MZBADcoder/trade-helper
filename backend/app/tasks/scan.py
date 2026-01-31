from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import db
from app.services.iv_scanner import scan_iv_for_ticker


@celery_app.task(name="app.tasks.scan.scan_iv")
def scan_iv() -> dict:
    tickers = [item["ticker"] for item in db.watchlist_list()]
    inserted = 0

    for ticker in tickers:
        for hit in scan_iv_for_ticker(ticker=ticker):
            if db.alerts_insert_once(
                ticker=hit.ticker,
                rule_key=hit.rule_key,
                priority=hit.priority,
                message=hit.message,
            ):
                inserted += 1

    return {
        "tickers": len(tickers),
        "alerts_inserted": inserted,
        "polygon_enabled": bool(settings.polygon_api_key),
    }

