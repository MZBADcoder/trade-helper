from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.auth.service import AuthApplicationService
from app.core.security import hash_password, verify_password
from app.domain.auth.constants import (
    ERROR_EMAIL_ALREADY_REGISTERED,
    ERROR_INVALID_EMAIL_OR_PASSWORD,
    ERROR_INVALID_USER_ID,
    ERROR_USER_INACTIVE,
)
from app.domain.auth.schemas import User, UserCredentials


class FakeAuthRepository:
    def __init__(self) -> None:
        self.by_email_normalized: dict[str, UserCredentials] = {}
        self.created_payload: dict[str, str] | None = None
        self.updated_user_id: int | None = None

    def create_user(
        self,
        *,
        email: str,
        email_normalized: str,
        password_hash: str,
    ) -> User:
        self.created_payload = {
            "email": email,
            "email_normalized": email_normalized,
            "password_hash": password_hash,
        }
        now = datetime.now(tz=timezone.utc)
        user = User(
            id=1,
            email=email,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )
        self.by_email_normalized[email_normalized] = UserCredentials(
            id=user.id,
            email=user.email,
            email_normalized=email_normalized,
            password_hash=password_hash,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )
        return user

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None:
        return self.by_email_normalized.get(email_normalized)

    def get_user_by_id(self, *, user_id: int) -> User | None:
        for user in self.by_email_normalized.values():
            if user.id == user_id:
                return User(
                    id=user.id,
                    email=user.email,
                    is_active=user.is_active,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    last_login_at=user.last_login_at,
                )
        return None

    def update_last_login(self, *, user_id: int) -> User | None:
        self.updated_user_id = user_id
        current = self.get_user_by_id(user_id=user_id)
        if current is None:
            return None
        return User(
            id=current.id,
            email=current.email,
            is_active=current.is_active,
            created_at=current.created_at,
            updated_at=current.updated_at,
            last_login_at=datetime.now(tz=timezone.utc),
        )


class FakeUoW:
    def __init__(self, *, auth_repo: FakeAuthRepository) -> None:
        self.auth_repo = auth_repo
        self.watchlist_repo = None
        self.market_data_repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_register_normalizes_email_and_hashes_password() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    created = service.register(email=" Trader@Example.com ", password="StrongPass123")

    assert created.email == "Trader@Example.com"
    assert repo.created_payload is not None
    assert repo.created_payload["email_normalized"] == "trader@example.com"
    assert repo.created_payload["password_hash"] != "StrongPass123"
    assert verify_password("StrongPass123", repo.created_payload["password_hash"])


def test_register_rejects_duplicate_email() -> None:
    repo = FakeAuthRepository()
    repo.by_email_normalized["trader@example.com"] = UserCredentials(
        id=10,
        email="trader@example.com",
        email_normalized="trader@example.com",
        password_hash=hash_password("StrongPass123"),
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        last_login_at=None,
    )
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    with pytest.raises(ValueError, match=ERROR_EMAIL_ALREADY_REGISTERED):
        service.register(email="Trader@example.com", password="StrongPass123")


def test_authenticate_updates_last_login_when_credentials_valid() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))
    service.register(email="trader@example.com", password="StrongPass123")

    user = service.login(email="TRADER@example.com", password="StrongPass123")

    assert user.access_token
    assert repo.updated_user_id == 1


def test_authenticate_rejects_invalid_or_inactive_user() -> None:
    repo = FakeAuthRepository()
    repo.by_email_normalized["trader@example.com"] = UserCredentials(
        id=2,
        email="trader@example.com",
        email_normalized="trader@example.com",
        password_hash=hash_password("StrongPass123"),
        is_active=False,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        last_login_at=None,
    )
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login(email="trader@example.com", password="wrong-pass")

    with pytest.raises(ValueError, match=ERROR_USER_INACTIVE):
        service.login(email="trader@example.com", password="StrongPass123")


def test_get_user_rejects_invalid_user_id() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    with pytest.raises(ValueError, match=ERROR_INVALID_USER_ID):
        service.get_user(user_id=0)
