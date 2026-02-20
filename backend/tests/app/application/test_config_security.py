from __future__ import annotations

import pytest

from app.core.config import Settings


def test_settings_rejects_placeholder_secret_key() -> None:
    settings = Settings(app_secret_key="change-me", app_env="dev")
    assert settings.app_secret_key != "change-me"
    assert len(settings.app_secret_key) >= 32

    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Settings(app_secret_key="change-me", app_env="prod")

    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Settings(app_secret_key=None, app_env="prod")


def test_settings_accepts_strong_secret_key() -> None:
    settings = Settings(app_secret_key="s" * 32)
    assert settings.app_secret_key == "s" * 32
