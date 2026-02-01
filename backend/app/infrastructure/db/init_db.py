from __future__ import annotations

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import engine

# Ensure models are registered with SQLAlchemy metadata.
from app.infrastructure.db import models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
