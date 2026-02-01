from __future__ import annotations

from app.application.alerts.interfaces import AlertsApplicationService
from app.domain.alerts.interfaces import AlertsService


class DefaultAlertsApplicationService(AlertsApplicationService):
    def __init__(self, *, service: AlertsService | None = None) -> None:
        self._service = service

    def list_alerts(self, *, limit: int) -> list[dict]:
        raise NotImplementedError("alerts application service not implemented")

    def insert_once(
        self,
        *,
        ticker: str,
        rule_key: str,
        priority: str,
        message: str,
    ) -> bool:
        raise NotImplementedError("alerts application service not implemented")
