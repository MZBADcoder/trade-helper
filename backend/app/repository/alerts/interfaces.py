from __future__ import annotations

from typing import Protocol


class AlertsRepository(Protocol):
    def list_alerts(self, *, limit: int) -> list[dict]: ...

    def insert_once(
        self,
        *,
        ticker: str,
        rule_key: str,
        priority: str,
        message: str,
    ) -> bool: ...
