from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.security import verify_password
from app.application.auth.login_throttle import AuthLoginThrottle
from app.application.auth.service import AuthApplicationService
from app.domain.auth.constants import (
    ERROR_AUTH_RATE_LIMITED,
    ERROR_EMAIL_ALREADY_REGISTERED,
    ERROR_INVALID_EMAIL_OR_PASSWORD,
    ERROR_INVALID_USER_ID,
)
from app.domain.auth.schemas import User, UserCredentials


class FakeAuthRepository:
    def __init__(self) -> None:
        self._users: dict[int, UserCredentials] = {}
        self._email_index: dict[str, int] = {}
        self._next_id = 1
        self.created_payload: dict[str, str] | None = None

    def create_user(self, *, email: str, email_normalized: str, password_hash: str) -> User:
        if email_normalized in self._email_index:
            raise ValueError(ERROR_EMAIL_ALREADY_REGISTERED)

        self.created_payload = {
            "email": email,
            "email_normalized": email_normalized,
            "password_hash": password_hash,
        }
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


class FakeUoW:
    def __init__(self, *, auth_repo: FakeAuthRepository) -> None:
        self.auth_repo = auth_repo
        self.market_data_repo = None
        self.watchlist_repo = None
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_register_normalizes_email_and_hashes_password() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    created = service.register(email=" Trader@Example.com ", password="StrongPass123")

    assert created.email == "Trader@Example.com"
    assert repo.created_payload is not None
    assert repo.created_payload["email_normalized"] == "trader@example.com"
    assert repo.created_payload["password_hash"] != "StrongPass123"
    assert verify_password("StrongPass123", repo.created_payload["password_hash"])


def test_register_and_login_issue_valid_access_token() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    created = service.register(email="Trader@Example.com", password="strong-pass-123")
    token = service.login(email="trader@example.com", password="strong-pass-123")
    current_user = service.get_current_user_from_token(token=token.access_token)

    assert created.email == "Trader@Example.com"
    assert token.expires_in == 14 * 24 * 60 * 60
    assert current_user.id == created.id
    assert current_user.last_login_at is not None


def test_login_rejects_wrong_password() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))
    service.register(email="trader@example.com", password="strong-pass-123")

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login(email="trader@example.com", password="wrong-password")


def test_login_returns_generic_error_for_inactive_user() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))
    created = service.register(email="trader@example.com", password="strong-pass-123")
    credentials = repo.get_user_by_email_normalized(email_normalized="trader@example.com")
    assert credentials is not None
    credentials.is_active = False

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login(email=created.email, password="strong-pass-123")


def test_login_throttle_blocks_after_repeated_failures() -> None:
    repo = FakeAuthRepository()
    throttle = AuthLoginThrottle(max_failures=2, window_seconds=60, block_seconds=300)
    service = AuthApplicationService(
        uow=FakeUoW(auth_repo=repo),
        login_throttle=throttle,
    )
    service.register(email="trader@example.com", password="strong-pass-123")

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login(email="trader@example.com", password="wrong-password")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        service.login(email="trader@example.com", password="wrong-password")


def test_login_throttle_blocks_repeated_failures_from_same_source() -> None:
    repo = FakeAuthRepository()
    throttle = AuthLoginThrottle(max_failures=2, window_seconds=60, block_seconds=300)
    service = AuthApplicationService(
        uow=FakeUoW(auth_repo=repo),
        login_throttle=throttle,
    )
    service.register(email="trader@example.com", password="strong-pass-123")

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login_with_source(
            email="trader@example.com",
            password="wrong-password",
            source="203.0.113.10",
        )

    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        service.login_with_source(
            email="rotating@example.com",
            password="wrong-password",
            source="203.0.113.10",
        )


def test_successful_login_clears_source_throttle_bucket() -> None:
    repo = FakeAuthRepository()
    throttle = AuthLoginThrottle(max_failures=2, window_seconds=60, block_seconds=300)
    service = AuthApplicationService(
        uow=FakeUoW(auth_repo=repo),
        login_throttle=throttle,
    )
    service.register(email="trader@example.com", password="strong-pass-123")

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login_with_source(
            email="trader@example.com",
            password="wrong-password",
            source="203.0.113.10",
        )

    service.login_with_source(
        email="trader@example.com",
        password="strong-pass-123",
        source="203.0.113.10",
    )

    with pytest.raises(ValueError, match=ERROR_INVALID_EMAIL_OR_PASSWORD):
        service.login_with_source(
            email="missing@example.com",
            password="wrong-password",
            source="203.0.113.10",
        )


def test_get_user_rejects_invalid_user_id() -> None:
    repo = FakeAuthRepository()
    service = AuthApplicationService(uow=FakeUoW(auth_repo=repo))

    with pytest.raises(ValueError, match=ERROR_INVALID_USER_ID):
        service.get_user(user_id=0)
