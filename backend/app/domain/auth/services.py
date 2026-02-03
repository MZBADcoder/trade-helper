from __future__ import annotations

from app.core.security import hash_password, normalize_email, verify_password
from app.domain.auth.constants import (
    ERROR_EMAIL_ALREADY_REGISTERED,
    ERROR_INVALID_EMAIL_OR_PASSWORD,
    ERROR_INVALID_USER_ID,
    ERROR_USER_INACTIVE,
)
from app.domain.auth.schemas import User, UserCredentials
from app.repository.auth.interfaces import AuthRepository


class DefaultAuthService:
    def __init__(self, *, repository: AuthRepository) -> None:
        if repository is None:
            raise ValueError("repository is required")
        self._repository: AuthRepository = repository

    def register(self, *, email: str, password: str) -> User:
        normalized_email = normalize_email(email)
        if self._repository.get_user_by_email_normalized(email_normalized=normalized_email) is not None:
            raise ValueError(ERROR_EMAIL_ALREADY_REGISTERED)

        password_hash = hash_password(password)
        return self._repository.create_user(
            email=email.strip(),
            email_normalized=normalized_email,
            password_hash=password_hash,
        )

    def authenticate(self, *, email: str, password: str) -> User:
        normalized_email = normalize_email(email)
        user = self._repository.get_user_by_email_normalized(email_normalized=normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError(ERROR_INVALID_EMAIL_OR_PASSWORD)
        if not user.is_active:
            raise ValueError(ERROR_USER_INACTIVE)

        updated_user = self._repository.update_last_login(user_id=user.id)
        if updated_user is not None:
            return updated_user
        return _credentials_to_user(user)

    def get_user(self, *, user_id: int) -> User | None:
        if user_id < 1:
            raise ValueError(ERROR_INVALID_USER_ID)
        return self._repository.get_user_by_id(user_id=user_id)


def _credentials_to_user(user: UserCredentials) -> User:
    return User(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )
