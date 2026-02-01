from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    raise NotImplementedError("db session not implemented")
