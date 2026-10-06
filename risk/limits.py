"""Risk limits — daily loss, max trades, drawdown circuit breaker."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from typing import List

from core.exceptions import RiskLimitError
from core.utils import now_utc


@dataclass
class DailyStats:
    date: str
    wins: int = 0
    losses: int = 0
    pnl_usd: float = 0.0
    signals_sent: int = 0


class RiskLimits:
    """Enforces daily/weekly risk limits and trading halts."""

    def __init__(self,
                 max_daily_losses: int = 3,
                 max_daily_loss_pct: float = 5.0,
                 max_drawdown_pct: float = 15.0,
                 max_signals_per_day: int = 20,
                 account_balance: float = 1000.0):
        self.max_daily_losses = max_daily_losses
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_signals_per_day = max_signals_per_day
        self.initial_balance = account_balance
        self.peak_balance = account_balance
        self.current_balance = account_balance
        self._daily: DailyStats = self._new_daily()
        self.halted = False
        self.halt_reason = ""

    def _new_daily(self) -> DailyStats:
        return DailyStats(date=now_utc().strftime("%Y-%m-%d"))

    def _rollover_if_needed(self) -> None:
        today = now_utc().strftime("%Y-%m-%d")
        if self._daily.date != today:
            self._daily = self._new_daily()
            self.halted = False
            self.halt_reason = ""

    @property
    def daily_stats(self) -> DailyStats:
        self._rollover_if_needed()
        return self._daily

    def can_trade(self) -> tuple:
        """Return (allowed, reason)."""
        self._rollover_if_needed()
        if self.halted:
            return False, f"Trading halted: {self.halt_reason}"
        if self._daily.losses >= self.max_daily_losses:
            return False, f"Daily loss limit reached ({self._daily.losses}/{self.max_daily_losses})"
        daily_loss_pct = abs(min(0, self._daily.pnl_usd)) / self.initial_balance * 100
        if daily_loss_pct >= self.max_daily_loss_pct:
            return False, f"Daily loss % limit reached ({daily_loss_pct:.1f}%)"
        if self._daily.signals_sent >= self.max_signals_per_day:
            return False, f"Daily signal cap reached ({self._daily.signals_sent})"
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
        if drawdown >= self.max_drawdown_pct:
            return False, f"Max drawdown reached ({drawdown:.1f}%)"
        return True, "OK"

    def record_signal(self) -> None:
        self._rollover_if_needed()
        self._daily.signals_sent += 1

    def record_trade_result(self, pnl_usd: float) -> None:
        self._rollover_if_needed()
        self._daily.pnl_usd += pnl_usd
        self.current_balance += pnl_usd
        self.peak_balance = max(self.peak_balance, self.current_balance)
        if pnl_usd > 0:
            self._daily.wins += 1
        elif pnl_usd < 0:
            self._daily.losses += 1

        # Check halt conditions
        if self._daily.losses >= self.max_daily_losses:
            self.halted = True
            self.halt_reason = f"{self._daily.losses} consecutive/ daily losses"
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
        if drawdown >= self.max_drawdown_pct:
            self.halted = True
            self.halt_reason = f"Drawdown {drawdown:.1f}% >= {self.max_drawdown_pct}%"

    def assert_can_trade(self) -> None:
        allowed, reason = self.can_trade()
        if not allowed:
            raise RiskLimitError(reason, limit_name="risk_limits")
