"""Repository — data access layer for all entities."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session

from core.logging_config import get_logger
from .models import Base, SignalRecord, TradeRecord, PerformanceSnapshot, BotStateRecord, init_db

logger = get_logger("database.repository")


class Repository:
    """Thin data-access wrapper over SQLAlchemy."""

    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
        init_db(database_url)
        self._Session = sessionmaker(bind=self.engine)

    def session(self) -> Session:
        return self._Session()

    # --- Signals ---
    def save_signal(self, signal) -> int:
        with self.session() as s:
            rec = SignalRecord(
                signal_id=signal.id, symbol=signal.symbol,
                direction=signal.direction.value, strength=signal.strength.value,
                entry=signal.entry, stop_loss=signal.stop_loss,
                take_profits=",".join(f"{tp:.2f}" for tp in signal.take_profits),
                risk_reward=signal.risk_reward, confluence_pct=signal.confluence_pct,
                timeframe=signal.timeframe, reasons=json.dumps(signal.reasons),
                atr=signal.atr, spread=signal.spread, session=signal.session,
                delivered=True,
            )
            s.add(rec)
            s.commit()
            return rec.id

    def recent_signals(self, limit: int = 10) -> List[SignalRecord]:
        with self.session() as s:
            return s.query(SignalRecord).order_by(desc(SignalRecord.created_at)).limit(limit).all()

    def signals_today(self) -> int:
        today = datetime.utcnow().date()
        with self.session() as s:
            return s.query(SignalRecord).filter(
                SignalRecord.created_at >= datetime(today.year, today.month, today.day)
            ).count()

    # --- Trades ---
    def save_trade(self, trade) -> int:
        with self.session() as s:
            rec = TradeRecord(
                signal_id=trade.get("signal_id", ""), symbol=trade.get("symbol", "XAUUSD"),
                direction=trade.get("direction", ""), entry_price=trade.get("entry", 0),
                exit_price=trade.get("exit", 0), stop_loss=trade.get("sl", 0),
                take_profit=trade.get("tp", 0), lot_size=trade.get("lot", 0.01),
                pnl_usd=trade.get("pnl", 0), status=trade.get("status", "OPEN"),
                exit_reason=trade.get("exit_reason", ""),
            )
            s.add(rec)
            s.commit()
            return rec.id

    def close_trade(self, signal_id: str, exit_price: float, pnl: float, reason: str) -> None:
        with self.session() as s:
            trade = s.query(TradeRecord).filter_by(signal_id=signal_id, status="OPEN").first()
            if trade:
                trade.exit_price = exit_price
                trade.pnl_usd = pnl
                trade.status = "CLOSED"
                trade.exit_reason = reason
                trade.closed_at = datetime.utcnow()
                s.commit()

    def open_trades(self) -> List[TradeRecord]:
        with self.session() as s:
            return s.query(TradeRecord).filter_by(status="OPEN").all()

    # --- Performance ---
    def save_snapshot(self, snapshot: dict) -> None:
        with self.session() as s:
            rec = PerformanceSnapshot(**snapshot)
            s.add(rec)
            s.commit()

    def performance_history(self, days: int = 30) -> List[PerformanceSnapshot]:
        since = datetime.utcnow() - timedelta(days=days)
        with self.session() as s:
            return s.query(PerformanceSnapshot).filter(PerformanceSnapshot.timestamp >= since).all()

    # --- Bot state KV ---
    def set_state(self, key: str, value: str) -> None:
        with self.session() as s:
            rec = s.query(BotStateRecord).filter_by(key=key).first()
            if rec:
                rec.value = value
            else:
                s.add(BotStateRecord(key=key, value=value))
            s.commit()

    def get_state(self, key: str, default: str = "") -> str:
        with self.session() as s:
            rec = s.query(BotStateRecord).filter_by(key=key).first()
            return rec.value if rec else default

    def daily_stats(self) -> dict:
        today = datetime.utcnow().date()
        start = datetime(today.year, today.month, today.day)
        with self.session() as s:
            trades = s.query(TradeRecord).filter(TradeRecord.opened_at >= start).all()
            wins = sum(1 for t in trades if t.pnl_usd > 0)
            losses = sum(1 for t in trades if t.pnl_usd < 0)
            pnl = sum(t.pnl_usd for t in trades)
            signals = s.query(SignalRecord).filter(SignalRecord.created_at >= start).count()
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        return {"signals_sent": signals, "wins": wins, "losses": losses,
                "pnl": round(pnl, 2), "win_rate": round(wr, 1), "max_dd": 0.0}
