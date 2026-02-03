from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.auth.service import DefaultAuthApplicationService
from app.domain.auth.schemas import User, UserCredentials


class FakeAuthRepository:
    def __init__(self) -> None:
        self._users: dict[int, UserCredentials] = {}
        self._email_index: dict[str, int] = {}
        self._next_id = 1

    def create_user(self, *, email: str, email_normalized: str, password_hash: str) -> User:
        if email_normalized in self._email_index:
            raise ValueError("Email already registered")

        user_id = self._next_id
        self._next_id += 1
        now = datetime.now(tz=timezone.utc)
        record = UserCredentials(
            id=user_id,
            email=email,
            email_normalized=email_normalized,
            password_hash=password_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )
        self._users[user_id] = record
        self._email_index[email_normalized] = user_id
        return self._to_user(record)

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None:
        user_id = self._email_index.get(email_normalized)
        if user_id is None:
            return None
        return self._users[user_id]

    def get_user_by_id(self, *, user_id: int) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        return self._to_user(user)

    def update_last_login(self, *, user_id: int) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        user.last_login_at = datetime.now(tz=timezone.utc)
        return self._to_user(user)

    @staticmethod
    def _to_user(user: UserCredentials) -> User:
        return User(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )


def test_register_and_login_issue_valid_access_token() -> None:
    repo = FakeAuthRepository()
    service = DefaultAuthApplicationService(repository=repo)

    created = service.register(email="Trader@Example.com", password="strong-pass-123")
    token = service.login(email="trader@example.com", password="strong-pass-123")
    current_user = service.get_current_user_from_token(token=token.access_token)

    assert created.email == "Trader@Example.com"
    assert token.expires_in == 14 * 24 * 60 * 60
    assert current_user.id == created.id
    assert current_user.last_login_at is not None


def test_login_rejects_wrong_password() -> None:
    repo = FakeAuthRepository()
    service = DefaultAuthApplicationService(repository=repo)
    service.register(email="trader@example.com", password="strong-pass-123")

    with pytest.raises(ValueError, match="Invalid email or password"):
        service.login(email="trader@example.com", password="wrong-password")
