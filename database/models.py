"""SQLAlchemy ORM models."""
from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, create_engine,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SignalRecord(Base):
    """Persisted trading signal."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(16), index=True)
    symbol = Column(String(16), index=True)
    direction = Column(String(8))
    strength = Column(String(16))
    entry = Column(Float)
    stop_loss = Column(Float)
    take_profits = Column(String(256))  # comma-separated
    risk_reward = Column(Float)
    confluence_pct = Column(Float)
    timeframe = Column(String(8))
    reasons = Column(Text)
    atr = Column(Float)
    spread = Column(Float)
    session = Column(String(32))
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    delivered = Column(Boolean, default=False)
    outcome = Column(String(16), default="OPEN")  # OPEN/WIN/LOSS


class TradeRecord(Base):
    """Simulated/actual trade outcome."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(16), index=True)
    symbol = Column(String(16))
    direction = Column(String(8))
    entry_price = Column(Float)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    lot_size = Column(Float)
    pnl_usd = Column(Float, default=0.0)
    status = Column(String(16), default="OPEN")  # OPEN/CLOSED
    exit_reason = Column(String(16))  # TP/SL/BE/MANUAL
    opened_at = Column(DateTime, default=dt.datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class PerformanceSnapshot(Base):
    """Periodic performance snapshot for the dashboard."""
    __tablename__ = "performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)
    total_signals = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    win_rate_pct = Column(Float)
    total_pnl_usd = Column(Float)
    max_drawdown_pct = Column(Float)
    profit_factor = Column(Float)
    sharpe_ratio = Column(Float)


class BotStateRecord(Base):
    """Key-value bot state persistence."""
    __tablename__ = "bot_state"

    key = Column(String(64), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


def init_db(database_url: str) -> None:
    """Create all tables."""
    engine = create_engine(database_url, connect_args={"check_same_thread": False}
                           if database_url.startswith("sqlite") else {})
    Base.metadata.create_all(engine)
