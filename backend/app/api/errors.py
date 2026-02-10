from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict | None = None


def raise_api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> None:
    raise ApiError(status_code=status_code, code=code, message=message, details=details)


def install_api_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def _handle_api_error(_, exc: ApiError) -> JSONResponse:  # type: ignore[override]
        error_payload: dict = {
            "code": exc.code,
            "message": exc.message,
        }
        if exc.details is not None:
            error_payload["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content={"error": error_payload})
