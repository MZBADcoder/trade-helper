from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class User:
    id: int
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


@dataclass(slots=True)
class UserCredentials:
    id: int
    email: str
    email_normalized: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


@dataclass(slots=True)
class AccessToken:
    access_token: str
    expires_in: int
    token_type: str = "bearer"
