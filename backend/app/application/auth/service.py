from __future__ import annotations

from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.domain.auth.constants import ERROR_INVALID_TOKEN
from app.domain.auth.interfaces import AuthService
from app.domain.auth.schemas import AccessToken, User
from app.domain.auth.services import DefaultAuthService
from app.repository.auth.interfaces import AuthRepository


class DefaultAuthApplicationService:
    def __init__(
        self,
        *,
        service: AuthService | None = None,
        repository: AuthRepository | None = None,
    ) -> None:
        self._service = service
        self._repository = repository

    def register(self, *, email: str, password: str) -> User:
        return self._resolve_service().register(email=email, password=password)

    def login(self, *, email: str, password: str) -> AccessToken:
        user = self._resolve_service().authenticate(email=email, password=password)
        expires_in = settings.auth_access_token_expire_days * 24 * 60 * 60
        token = create_access_token(
            subject=str(user.id),
            secret_key=settings.app_secret_key,
            expires_delta=timedelta(seconds=expires_in),
        )
        return AccessToken(access_token=token, expires_in=expires_in)

    def get_user(self, *, user_id: int) -> User | None:
        return self._resolve_service().get_user(user_id=user_id)

    def get_current_user_from_token(self, *, token: str) -> User:
        payload = decode_access_token(token=token, secret_key=settings.app_secret_key)
        subject = payload.get("sub")
        try:
            user_id = int(subject)
        except (TypeError, ValueError) as exc:
            raise ValueError(ERROR_INVALID_TOKEN) from exc

        user = self.get_user(user_id=user_id)
        if user is None or not user.is_active:
            raise ValueError(ERROR_INVALID_TOKEN)
        return user

    def _resolve_service(self) -> AuthService:
        if self._service is not None:
            return self._service
        if self._repository is None:
            raise ValueError("repository is required")
        return DefaultAuthService(repository=self._repository)
