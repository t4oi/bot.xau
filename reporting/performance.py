"""Performance tracker — aggregates trade results over time."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PeriodStats:
    period: str
    signals: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total * 100 if total > 0 else 0.0


class PerformanceTracker:
    """Tracks and aggregates trade performance by period."""

    def __init__(self):
        self.trades: List[dict] = []
        self.by_day: Dict[str, PeriodStats] = defaultdict(lambda: PeriodStats(period=""))

    def record(self, signal_id: str, pnl_usd: float, day: str) -> None:
        self.trades.append({"signal_id": signal_id, "pnl": pnl_usd, "day": day})
        stats = self.by_day[day]
        stats.period = day
        stats.signals += 1
        if pnl_usd > 0:
            stats.wins += 1
        elif pnl_usd < 0:
            stats.losses += 1
        stats.pnl += pnl_usd
        stats.best_trade = max(stats.best_trade, pnl_usd)
        stats.worst_trade = min(stats.worst_trade, pnl_usd)

    def summary(self) -> dict:
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        total_pnl = sum(t["pnl"] for t in self.trades)
        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "win_rate": round(wins / total_trades * 100, 1) if total_trades else 0,
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / total_trades, 2) if total_trades else 0,
            "best": max((t["pnl"] for t in self.trades), default=0),
            "worst": min((t["pnl"] for t in self.trades), default=0),
            "days_active": len(self.by_day),
        }

    def streak(self) -> dict:
        cur_w = cur_l = max_w = max_l = 0
        for t in self.trades:
            if t["pnl"] > 0:
                cur_w += 1; cur_l = 0; max_w = max(max_w, cur_w)
            else:
                cur_l += 1; cur_w = 0; max_l = max(max_l, cur_l)
        return {"current_wins": cur_w, "current_losses": cur_l,
                "max_consecutive_wins": max_w, "max_consecutive_losses": max_l}
