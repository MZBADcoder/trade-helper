from __future__ import annotations

from app.api.dto.alerts import AlertOut
from app.domain.alerts.schemas import Alert


def to_domain_alert(dto: AlertOut) -> Alert:
    return Alert(**dto.model_dump())


def to_dto(alert: Alert) -> AlertOut:
    return AlertOut(**alert.model_dump())
