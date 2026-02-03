"""initial schema

Revision ID: f1a0e7d9c001
Revises: None
Create Date: 2026-02-03 23:37:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f1a0e7d9c001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.create_table(
        "market_bars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("timespan", sa.String(length=10), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
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
        sa.UniqueConstraint("ticker", "timespan", "multiplier", "start_at", name="uq_market_bar_key"),
    )
    op.create_index("ix_market_bars_ticker", "market_bars", ["ticker"], unique=False)
    op.create_index("ix_market_bars_timespan", "market_bars", ["timespan"], unique=False)
    op.create_index("ix_market_bars_start_at", "market_bars", ["start_at"], unique=False)
    op.create_index(
        "ix_market_bars_lookup",
        "market_bars",
        ["ticker", "timespan", "multiplier", "start_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_bars_lookup", table_name="market_bars")
    op.drop_index("ix_market_bars_start_at", table_name="market_bars")
    op.drop_index("ix_market_bars_timespan", table_name="market_bars")
    op.drop_index("ix_market_bars_ticker", table_name="market_bars")
    op.drop_table("market_bars")
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_table("users")
