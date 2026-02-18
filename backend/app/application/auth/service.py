from __future__ import annotations

from datetime import timedelta

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.domain.auth.constants import (
    ERROR_EMAIL_ALREADY_REGISTERED,
    ERROR_INVALID_EMAIL_OR_PASSWORD,
    ERROR_INVALID_TOKEN,
    ERROR_INVALID_USER_ID,
    ERROR_USER_INACTIVE,
)
from app.domain.auth.schemas import AccessToken, User, UserCredentials
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class AuthApplicationService:
    def __init__(self, *, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def register(self, *, email: str, password: str) -> User:
        normalized_email = normalize_email(email)
        with self._uow as uow:
            repo = _require_auth_repo(uow)
            if repo.get_user_by_email_normalized(email_normalized=normalized_email) is not None:
                raise ValueError(ERROR_EMAIL_ALREADY_REGISTERED)
            password_hash = hash_password(password)
            user = repo.create_user(
                email=email.strip(),
                email_normalized=normalized_email,
                password_hash=password_hash,
            )
            uow.commit()
            return user

    def login(self, *, email: str, password: str) -> AccessToken:
        user = self._authenticate(email=email, password=password)
        expires_in = settings.auth_access_token_expire_days * 24 * 60 * 60
        token = create_access_token(
            subject=str(user.id),
            secret_key=settings.app_secret_key,
            expires_delta=timedelta(seconds=expires_in),
        )
        return AccessToken(access_token=token, token_type="bearer", expires_in=expires_in)

    def get_user(self, *, user_id: int) -> User | None:
        if user_id < 1:
            raise ValueError(ERROR_INVALID_USER_ID)
        with self._uow as uow:
            repo = _require_auth_repo(uow)
            return repo.get_user_by_id(user_id=user_id)

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

    def _authenticate(self, *, email: str, password: str) -> User:
        normalized_email = normalize_email(email)
        with self._uow as uow:
            repo = _require_auth_repo(uow)
            user = repo.get_user_by_email_normalized(email_normalized=normalized_email)
            if user is None or not verify_password(password, user.password_hash):
                raise ValueError(ERROR_INVALID_EMAIL_OR_PASSWORD)
            if not user.is_active:
                raise ValueError(ERROR_USER_INACTIVE)

            updated_user = repo.update_last_login(user_id=user.id)
            uow.commit()
            if updated_user is not None:
                return updated_user
            return _credentials_to_user(user)


def _require_auth_repo(uow: SqlAlchemyUnitOfWork):
    if uow.auth_repo is None:
        raise RuntimeError("Auth repository not configured")
    return uow.auth_repo


def _credentials_to_user(user: UserCredentials) -> User:
    return User(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )
