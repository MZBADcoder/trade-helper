from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service, get_current_user
from app.api.v1.dto.auth import AccessTokenOut, LoginRequest, RegisterRequest, UserOut
from app.application.auth.service import DefaultAuthApplicationService
from app.domain.auth.constants import ERROR_EMAIL_ALREADY_REGISTERED
from app.domain.auth.schemas import User

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    service: DefaultAuthApplicationService = Depends(get_auth_service),
) -> UserOut:
    try:
        return service.register(email=payload.email, password=payload.password)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_409_CONFLICT if detail == ERROR_EMAIL_ALREADY_REGISTERED else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/login", response_model=AccessTokenOut)
def login(
    payload: LoginRequest,
    service: DefaultAuthApplicationService = Depends(get_auth_service),
) -> AccessTokenOut:
    try:
        return service.login(email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user
