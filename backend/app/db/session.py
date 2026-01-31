from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Alert, Rule, WatchlistItem


engine = create_engine(settings.database_url, pool_pre_ping=True)


@dataclass
class DB:
    def _session(self) -> Session:
        return Session(engine)

    def watchlist_list(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(select(WatchlistItem).order_by(WatchlistItem.ticker.asc())).scalars().all()
            return [{"ticker": r.ticker, "created_at": r.created_at} for r in rows]

    def watchlist_add(self, ticker: str) -> dict:
        ticker_norm = ticker.strip().upper()
        if not ticker_norm:
            raise ValueError("ticker required")
        with self._session() as session:
            existing = session.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker_norm)).scalar_one_or_none()
            if existing:
                raise ValueError("ticker already exists")
            session.execute(insert(WatchlistItem).values(ticker=ticker_norm))
            session.commit()
        return {"ticker": ticker_norm}

    def watchlist_remove(self, ticker: str) -> None:
        ticker_norm = ticker.strip().upper()
        with self._session() as session:
            session.execute(delete(WatchlistItem).where(WatchlistItem.ticker == ticker_norm))
            session.commit()

    def rules_list(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(select(Rule).order_by(Rule.id.asc())).scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "enabled": r.enabled,
                    "call_put": r.call_put,
                    "dte_bucket": r.dte_bucket,
                }
                for r in rows
            ]

    def rules_create(self, data: dict) -> dict:
        with self._session() as session:
            result = session.execute(insert(Rule).values(**data).returning(Rule))
            rule = result.scalar_one()
            session.commit()
            return {
                "id": rule.id,
                "name": rule.name,
                "enabled": rule.enabled,
                "call_put": rule.call_put,
                "dte_bucket": rule.dte_bucket,
            }

    def alerts_list(self, limit: int) -> list[dict]:
        with self._session() as session:
            rows = (
                session.execute(select(Alert).order_by(Alert.created_at.desc()).limit(limit))
                .scalars()
                .all()
            )
            return [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "rule_key": a.rule_key,
                    "priority": a.priority,
                    "message": a.message,
                    "created_at": a.created_at,
                }
                for a in rows
            ]

    def alerts_insert_once(self, *, ticker: str, rule_key: str, priority: str, message: str) -> bool:
        with self._session() as session:
            existing = (
                session.execute(select(Alert).where(Alert.ticker == ticker, Alert.rule_key == rule_key)).scalar_one_or_none()
            )
            if existing:
                return False
            session.execute(
                insert(Alert).values(
                    ticker=ticker,
                    rule_key=rule_key,
                    priority=priority,
                    message=message,
                )
            )
            session.commit()
            return True


db = DB()

