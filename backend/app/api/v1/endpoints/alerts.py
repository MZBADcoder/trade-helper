from fastapi import APIRouter

from app.application.alerts.service import DefaultAlertsApplicationService
from app.api.dto.alerts import AlertOut

router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(limit: int = 50) -> list[AlertOut]:
    service = DefaultAlertsApplicationService()
    alerts = service.list_alerts(limit=limit)
    return [AlertOut(**alert) for alert in alerts]
