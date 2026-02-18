from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class MarketBarDayModel(Base):
    __tablename__ = "market_bars_day"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="massive", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "trade_date", name="uq_market_bars_day_ticker_trade_date"),
        Index("ix_market_bars_day_lookup", "ticker", "trade_date", "start_at"),
    )


class MarketBarMinuteModel(Base):
    __tablename__ = "market_bars_minute"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="massive", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "start_at", name="uq_market_bars_minute_ticker_start_at"),
        Index("ix_market_bars_minute_lookup", "ticker", "trade_date", "start_at"),
    )


class MarketBarMinuteAggModel(Base):
    __tablename__ = "market_bars_minute_agg"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False)
    bucket_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    bucket_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="db_agg", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "multiplier",
            "bucket_start_at",
            name="uq_market_bars_minute_agg_ticker_multiplier_start",
        ),
        Index(
            "ix_market_bars_minute_agg_lookup",
            "ticker",
            "trade_date",
            "multiplier",
            "bucket_start_at",
        ),
    )
