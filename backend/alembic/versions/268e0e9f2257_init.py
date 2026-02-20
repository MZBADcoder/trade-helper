"""init

Revision ID: 268e0e9f2257
Revises: 
Create Date: 2026-02-20 23:45:45.963885
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '268e0e9f2257'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_bars_day",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "trade_date", name="uq_market_bars_day_ticker_trade_date"),
    )
    op.create_index("ix_market_bars_day_start_at", "market_bars_day", ["start_at"], unique=False)
    op.create_index("ix_market_bars_day_ticker", "market_bars_day", ["ticker"], unique=False)
    op.create_index("ix_market_bars_day_trade_date", "market_bars_day", ["trade_date"], unique=False)
    op.create_index(
        "ix_market_bars_day_lookup",
        "market_bars_day",
        ["ticker", "trade_date", "start_at"],
        unique=False,
    )

    op.create_table(
        "market_bars_minute",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "start_at", name="uq_market_bars_minute_ticker_start_at"),
    )
    op.create_index("ix_market_bars_minute_start_at", "market_bars_minute", ["start_at"], unique=False)
    op.create_index("ix_market_bars_minute_ticker", "market_bars_minute", ["ticker"], unique=False)
    op.create_index("ix_market_bars_minute_trade_date", "market_bars_minute", ["trade_date"], unique=False)
    op.create_index(
        "ix_market_bars_minute_lookup",
        "market_bars_minute",
        ["ticker", "trade_date", "start_at"],
        unique=False,
    )

    op.create_table(
        "market_bars_minute_agg",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("bucket_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker",
            "multiplier",
            "bucket_start_at",
            name="uq_market_bars_minute_agg_ticker_multiplier_start",
        ),
    )
    op.create_index(
        "ix_market_bars_minute_agg_bucket_start_at",
        "market_bars_minute_agg",
        ["bucket_start_at"],
        unique=False,
    )
    op.create_index("ix_market_bars_minute_agg_ticker", "market_bars_minute_agg", ["ticker"], unique=False)
    op.create_index(
        "ix_market_bars_minute_agg_trade_date",
        "market_bars_minute_agg",
        ["trade_date"],
        unique=False,
    )
    op.create_index(
        "ix_market_bars_minute_agg_lookup",
        "market_bars_minute_agg",
        ["ticker", "trade_date", "multiplier", "bucket_start_at"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_items_user_ticker"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_table("users")

    op.drop_index("ix_market_bars_minute_agg_lookup", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_trade_date", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_ticker", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_bucket_start_at", table_name="market_bars_minute_agg")
    op.drop_table("market_bars_minute_agg")

    op.drop_index("ix_market_bars_minute_lookup", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_trade_date", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_ticker", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_start_at", table_name="market_bars_minute")
    op.drop_table("market_bars_minute")

    op.drop_index("ix_market_bars_day_lookup", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_trade_date", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_ticker", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_start_at", table_name="market_bars_day")
    op.drop_table("market_bars_day")
