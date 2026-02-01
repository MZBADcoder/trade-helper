from fastapi import APIRouter

router = APIRouter()


@router.post("/enqueue")
def enqueue_scan() -> dict:
    raise NotImplementedError("scan endpoint not implemented")
