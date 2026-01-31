from fastapi import APIRouter

from app.db.session import db
from app.schemas.alerts import AlertOut

router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(limit: int = 50) -> list[AlertOut]:
    alerts = db.alerts_list(limit=limit)
    return [AlertOut(**alert) for alert in alerts]

