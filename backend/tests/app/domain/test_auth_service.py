from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.security import hash_password, verify_password
from app.domain.auth.constants import (
    ERROR_EMAIL_ALREADY_REGISTERED,
    ERROR_INVALID_EMAIL_OR_PASSWORD,
    ERROR_INVALID_USER_ID,
    ERROR_USER_INACTIVE,
)
from app.domain.auth.schemas import User, UserCredentials
from app.domain.auth.services import DefaultAuthService


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
            **user.model_dump(),
            email_normalized=email_normalized,
            password_hash=password_hash,
        )
        return user

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None:
        return self.by_email_normalized.get(email_normalized)

    def get_user_by_id(self, *, user_id: int) -> User | None:
        for user in self.by_email_normalized.values():
            if user.id == user_id:
                return User(**user.model_dump(exclude={"email_normalized", "password_hash"}))
        return None

    def update_last_login(self, *, user_id: int) -> User | None:
        self.updated_user_id = user_id
        current = self.get_user_by_id(user_id=user_id)
        if current is None:
            return None
        return User(
            **current.model_dump(exclude={"last_login_at"}),
            last_login_at=datetime.now(tz=timezone.utc),
        )


def test_register_normalizes_email_and_hashes_password() -> None:
    repo = FakeAuthRepository()
    service = DefaultAuthService(repository=repo)

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
    service = DefaultAuthService(repository=repo)

    with pytest.raises(ValueError, match=ERROR_EMAIL_ALREADY_REGISTERED):
        service.register(email="Trader@example.com", password="StrongPass123")


def test_authenticate_updates_last_login_when_credentials_valid() -> None:
    repo = FakeAuthRepository()
    service = DefaultAuthService(repository=repo)
    service.register(email="trader@example.com", password="StrongPass123")

    user = service.authenticate(email="TRADER@example.com", password="StrongPass123")

    assert user.last_login_at is not None
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
    service = DefaultAuthService(repository=repo)

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.authenticate(email="trader@example.com", password="wrong-pass")

    with pytest.raises(ValueError, match=ERROR_USER_INACTIVE):
        service.authenticate(email="trader@example.com", password="StrongPass123")


def test_get_user_rejects_invalid_user_id() -> None:
    repo = FakeAuthRepository()
    service = DefaultAuthService(repository=repo)

    with pytest.raises(ValueError, match=ERROR_INVALID_USER_ID):
        service.get_user(user_id=0)
