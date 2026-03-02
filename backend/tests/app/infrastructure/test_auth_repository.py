from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.user import UserModel
from app.infrastructure.repositories.auth_repository import SqlAlchemyAuthRepository


async def test_update_last_login_refreshes_model_before_mapping() -> None:
    now = datetime.now(tz=timezone.utc)
    user = UserModel(
        id=1,
        email="trader@example.com",
        email_normalized="trader@example.com",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )

    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = user
    repo = SqlAlchemyAuthRepository(session=session)

    result = await repo.update_last_login(user_id=1)

    session.add.assert_called_once_with(user)
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)
    assert result is not None
    assert result.id == 1
    assert result.last_login_at is not None


async def test_update_last_login_returns_none_when_user_not_found() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = None
    repo = SqlAlchemyAuthRepository(session=session)

    result = await repo.update_last_login(user_id=999)

    assert result is None
    session.flush.assert_not_awaited()
    session.refresh.assert_not_awaited()
