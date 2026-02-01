from __future__ import annotations

from app.repository.alerts.interfaces import AlertsRepository
from app.domain.alerts.interfaces import AlertsService


class DefaultAlertsService(AlertsService):
    def __init__(self, *, repository: AlertsRepository | None = None) -> None:
        self._repository = repository

    def list_alerts(self, *, limit: int) -> list[dict]:
        raise NotImplementedError("alerts service not implemented")

    def insert_once(
        self,
        *,
        ticker: str,
        rule_key: str,
        priority: str,
        message: str,
    ) -> bool:
        raise NotImplementedError("alerts service not implemented")
