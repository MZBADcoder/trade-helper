from pathlib import Path
import secrets

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_secret_key: str | None = None
    auth_access_token_expire_days: int = 14

    massive_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MASSIVE_API_KEY", "POLYGON_API_KEY"),
    )
    market_data_daily_lookback_days: int = 730
    market_data_intraday_lookback_days: int = 5
    market_data_enable_direct_fallback: bool = True
    market_data_minute_retention_trade_days: int = 10
    market_stream_max_symbols_per_connection: int = 100
    market_stream_queue_size: int = 512
    market_stream_ping_interval_seconds: int = 20
    market_stream_ping_timeout_seconds: int = 10
    market_stream_ping_max_misses: int = 2
    market_stream_redis_channel: str = "market:stocks:events"
    market_stream_registry_prefix: str = "market:stocks:subs"
    market_stream_registry_ttl_seconds: int = 30
    market_stream_registry_refresh_seconds: int = 10
    market_stream_realtime_reconcile_interval_seconds: int = 2
    market_stream_realtime_enabled: bool = True
    market_stream_delay_minutes: int = 15
    market_stream_gateway_instance_id: str | None = None
    options_data_enabled: bool = False

    postgres_db: str = "trader_helper"
    postgres_user: str = "trader_helper"
    postgres_password: str = "trader_helper"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    feishu_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None

    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def _validate_app_secret_key(self) -> "Settings":
        normalized = (self.app_secret_key or "").strip()
        insecure_placeholders = {
            "change-me",
            "changeme",
            "replace-me",
            "replace-with-strong-random-secret",
        }
        is_prod = self.app_env.lower() in {"prod", "production"}

        if not normalized:
            if is_prod:
                raise ValueError("APP_SECRET_KEY is required in production")
            normalized = secrets.token_urlsafe(48)

        if normalized.lower() in insecure_placeholders:
            if is_prod:
                raise ValueError("APP_SECRET_KEY must be replaced with a strong random secret in production")
            normalized = secrets.token_urlsafe(48)

        if len(normalized) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters")

        self.app_secret_key = normalized
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
