"""BE-0005 split market bars tables

Revision ID: 7f0a4a3028a1
Revises: f1a0e7d9c001
Create Date: 2026-02-18 10:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "7f0a4a3028a1"
down_revision = "f1a0e7d9c001"
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
    op.create_index("ix_market_bars_day_ticker", "market_bars_day", ["ticker"], unique=False)
    op.create_index("ix_market_bars_day_trade_date", "market_bars_day", ["trade_date"], unique=False)
    op.create_index("ix_market_bars_day_start_at", "market_bars_day", ["start_at"], unique=False)
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
    op.create_index("ix_market_bars_minute_ticker", "market_bars_minute", ["ticker"], unique=False)
    op.create_index("ix_market_bars_minute_trade_date", "market_bars_minute", ["trade_date"], unique=False)
    op.create_index("ix_market_bars_minute_start_at", "market_bars_minute", ["start_at"], unique=False)
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
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_market_bars_minute_agg_ticker", "market_bars_minute_agg", ["ticker"], unique=False)
    op.create_index("ix_market_bars_minute_agg_trade_date", "market_bars_minute_agg", ["trade_date"], unique=False)
    op.create_index("ix_market_bars_minute_agg_bucket_start_at", "market_bars_minute_agg", ["bucket_start_at"], unique=False)
    op.create_index(
        "ix_market_bars_minute_agg_lookup",
        "market_bars_minute_agg",
        ["ticker", "trade_date", "multiplier", "bucket_start_at"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO market_bars_day (
            ticker, trade_date, start_at, open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            (start_at AT TIME ZONE 'America/New_York')::date AS trade_date,
            start_at,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars
        WHERE timespan = 'day' AND multiplier = 1
        ON CONFLICT (ticker, trade_date) DO UPDATE SET
            start_at = excluded.start_at,
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            vwap = excluded.vwap,
            trades = excluded.trades,
            source = excluded.source
        """
    )
    op.execute(
        """
        INSERT INTO market_bars_minute (
            ticker, trade_date, start_at, open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            (start_at AT TIME ZONE 'America/New_York')::date AS trade_date,
            start_at,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars
        WHERE timespan = 'minute' AND multiplier = 1
        ON CONFLICT (ticker, start_at) DO UPDATE SET
            trade_date = excluded.trade_date,
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            vwap = excluded.vwap,
            trades = excluded.trades,
            source = excluded.source
        """
    )
    op.execute(
        """
        INSERT INTO market_bars_minute_agg (
            ticker, trade_date, multiplier, bucket_start_at, bucket_end_at, is_final,
            open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            (start_at AT TIME ZONE 'America/New_York')::date AS trade_date,
            multiplier,
            start_at AS bucket_start_at,
            start_at + make_interval(mins => multiplier) AS bucket_end_at,
            true AS is_final,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars
        WHERE timespan = 'minute' AND multiplier IN (5, 15, 60)
        ON CONFLICT (ticker, multiplier, bucket_start_at) DO UPDATE SET
            trade_date = excluded.trade_date,
            bucket_end_at = excluded.bucket_end_at,
            is_final = excluded.is_final,
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            vwap = excluded.vwap,
            trades = excluded.trades,
            source = excluded.source
        """
    )

    op.drop_index("ix_market_bars_lookup", table_name="market_bars")
    op.drop_index("ix_market_bars_start_at", table_name="market_bars")
    op.drop_index("ix_market_bars_timespan", table_name="market_bars")
    op.drop_index("ix_market_bars_ticker", table_name="market_bars")
    op.drop_table("market_bars")


def downgrade() -> None:
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

    op.execute(
        """
        INSERT INTO market_bars (
            ticker, timespan, multiplier, start_at, open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            'day' AS timespan,
            1 AS multiplier,
            start_at,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars_day
        ON CONFLICT (ticker, timespan, multiplier, start_at) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO market_bars (
            ticker, timespan, multiplier, start_at, open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            'minute' AS timespan,
            1 AS multiplier,
            start_at,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars_minute
        ON CONFLICT (ticker, timespan, multiplier, start_at) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO market_bars (
            ticker, timespan, multiplier, start_at, open, high, low, close, volume, vwap, trades, source
        )
        SELECT
            ticker,
            'minute' AS timespan,
            multiplier,
            bucket_start_at AS start_at,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            trades,
            source
        FROM market_bars_minute_agg
        ON CONFLICT (ticker, timespan, multiplier, start_at) DO NOTHING
        """
    )

    op.drop_index("ix_market_bars_minute_agg_lookup", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_bucket_start_at", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_trade_date", table_name="market_bars_minute_agg")
    op.drop_index("ix_market_bars_minute_agg_ticker", table_name="market_bars_minute_agg")
    op.drop_table("market_bars_minute_agg")

    op.drop_index("ix_market_bars_minute_lookup", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_start_at", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_trade_date", table_name="market_bars_minute")
    op.drop_index("ix_market_bars_minute_ticker", table_name="market_bars_minute")
    op.drop_table("market_bars_minute")

    op.drop_index("ix_market_bars_day_lookup", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_start_at", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_trade_date", table_name="market_bars_day")
    op.drop_index("ix_market_bars_day_ticker", table_name="market_bars_day")
    op.drop_table("market_bars_day")
