from fastapi import APIRouter

from app.core.celery_app import celery_app

router = APIRouter()


@router.post("/enqueue")
def enqueue_scan() -> dict:
    task = celery_app.send_task("app.tasks.scan.scan_iv")
    return {"task_id": task.id}

