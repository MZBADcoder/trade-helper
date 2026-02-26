from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service, get_current_user
from app.api.v1.dto.auth import AccessTokenOut, LoginRequest, RegisterAcceptedOut, RegisterRequest, UserOut
from app.api.v1.dto.mappers import to_access_token_out, to_user_out
from app.application.auth.service import AuthApplicationService
from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED, ERROR_EMAIL_ALREADY_REGISTERED
from app.domain.auth.schemas import User

router = APIRouter()


@router.post("/register", response_model=RegisterAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
def register(
    payload: RegisterRequest,
    service: AuthApplicationService = Depends(get_auth_service),
) -> RegisterAcceptedOut:
    try:
        service.register(email=payload.email, password=payload.password)
        return RegisterAcceptedOut()
    except ValueError as exc:
        detail = str(exc)
        if detail == ERROR_EMAIL_ALREADY_REGISTERED:
            # Keep response semantics uniform to avoid account enumeration.
            return RegisterAcceptedOut()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.post("/login", response_model=AccessTokenOut)
def login(
    payload: LoginRequest,
    service: AuthApplicationService = Depends(get_auth_service),
) -> AccessTokenOut:
    try:
        token = service.login(email=payload.email, password=payload.password)
        return to_access_token_out(token)
    except ValueError as exc:
        detail = str(exc)
        if detail == ERROR_AUTH_RATE_LIMITED:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail) from exc


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(current_user)
