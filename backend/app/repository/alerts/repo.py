from __future__ import annotations

from app.repository.alerts.interfaces import AlertsRepository


class SqlAlchemyAlertsRepository(AlertsRepository):
    def __init__(self, *, session: object | None = None) -> None:
        self._session = session

    def list_alerts(self, *, limit: int) -> list[dict]:
        raise NotImplementedError("alerts repository not implemented")

    def insert_once(
        self,
        *,
        ticker: str,
        rule_key: str,
        priority: str,
        message: str,
    ) -> bool:
        raise NotImplementedError("alerts repository not implemented")
