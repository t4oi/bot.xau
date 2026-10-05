"""Analytics queries — pre-built SQL queries for performance analysis."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func
from .models import SignalRecord, TradeRecord, PerformanceSnapshot


class AnalyticsQueries:
    """Pre-built analytics queries over the trade database."""

    def __init__(self, session_factory):
        self._Session = session_factory

    def win_rate_by_timeframe(self) -> Dict[str, dict]:
        with self._Session() as s:
            rows = s.query(
                SignalRecord.timeframe,
                func.count(SignalRecord.id),
                func.sum(func.case((SignalRecord.outcome == "WIN", 1), else_=0)),
                func.sum(func.case((SignalRecord.outcome == "LOSS", 1), else_=0)),
            ).group_by(SignalRecord.timeframe).all()
            result = {}
            for tf, total, wins, losses in rows:
                wr = wins / total * 100 if total else 0
                result[tf] = {"total": total, "wins": wins, "losses": losses, "win_rate": round(wr, 1)}
            return result

    def win_rate_by_hour(self) -> Dict[int, dict]:
        with self._Session() as s:
            rows = s.query(
                func.strftime("%H", SignalRecord.created_at).label("hour"),
                func.count(SignalRecord.id),
                func.sum(func.case((SignalRecord.outcome == "WIN", 1), else_=0)),
            ).group_by("hour").all()
            return {int(h): {"total": t, "wins": w, "win_rate": round(w / t * 100, 1) if t else 0}
                    for h, t, w in rows}

    def profit_by_day(self, days: int = 30) -> List[dict]:
        since = datetime.utcnow() - timedelta(days=days)
        with self._Session() as s:
            rows = s.query(
                func.date(TradeRecord.closed_at).label("day"),
                func.sum(TradeRecord.pnl_usd),
                func.count(TradeRecord.id),
            ).filter(TradeRecord.closed_at >= since).group_by("day").all()
            return [{"day": str(d), "pnl": round(p or 0, 2), "trades": t} for d, p, t in rows]

    def best_worst_signals(self, limit: int = 5) -> dict:
        with self._Session() as s:
            best = s.query(TradeRecord).order_by(TradeRecord.pnl_usd.desc()).limit(limit).all()
            worst = s.query(TradeRecord).order_by(TradeRecord.pnl_usd.asc()).limit(limit).all()
            return {
                "best": [{"signal_id": t.signal_id, "pnl": t.pnl_usd, "direction": t.direction} for t in best],
                "worst": [{"signal_id": t.signal_id, "pnl": t.pnl_usd, "direction": t.direction} for t in worst],
            }

    def expectancy_by_confluence_bucket(self) -> Dict[str, dict]:
        buckets = {"50-60": (50, 60), "60-70": (60, 70), "70-80": (70, 80), "80+": (80, 101)}
        result = {}
        with self._Session() as s:
            for name, (lo, hi) in buckets.items():
                signals = s.query(SignalRecord).filter(
                    SignalRecord.confluence_pct >= lo, SignalRecord.confluence_pct < hi
                ).all()
                wins = sum(1 for sig in signals if sig.outcome == "WIN")
                total = len(signals)
                result[name] = {"total": total, "win_rate": round(wins / total * 100, 1) if total else 0}
        return result

    def summary(self) -> dict:
        with self._Session() as s:
            total_signals = s.query(func.count(SignalRecord.id)).scalar() or 0
            total_trades = s.query(func.count(TradeRecord.id)).scalar() or 0
            total_pnl = s.query(func.sum(TradeRecord.pnl_usd)).scalar() or 0
            wins = s.query(func.count(TradeRecord.id)).filter(TradeRecord.pnl_usd > 0).scalar() or 0
            return {
                "total_signals": total_signals,
                "total_trades": total_trades,
                "total_pnl_usd": round(total_pnl, 2),
                "win_rate": round(wins / total_trades * 100, 1) if total_trades else 0,
            }
