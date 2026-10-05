"""Drawdown guard — tracks equity curve and scales risk after drawdown."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class DrawdownEvent:
    peak: float
    trough: float
    drawdown_pct: float
    duration_bars: int


class DrawdownGuard:
    """Monitors drawdown and dynamically adjusts risk multiplier."""

    def __init__(self, initial_balance: float = 1000.0,
                 dd_step_pct: float = 5.0, risk_reduction_factor: float = 0.5):
        self.peak = initial_balance
        self.equity_curve: List[float] = [initial_balance]
        self.dd_events: List[DrawdownEvent] = []
        self.dd_step_pct = dd_step_pct
        self.risk_reduction_factor = risk_reduction_factor

    @property
    def current_drawdown_pct(self) -> float:
        if self.peak <= 0:
            return 0.0
        current = self.equity_curve[-1]
        return (self.peak - current) / self.peak * 100.0

    @property
    def risk_multiplier(self) -> float:
        """Reduce risk as drawdown deepens."""
        dd = self.current_drawdown_pct
        steps = int(dd // self.dd_step_pct)
        return max(0.1, self.risk_reduction_factor ** steps)

    def update(self, equity: float) -> None:
        self.equity_curve.append(equity)
        if equity > self.peak:
            self.peak = equity

    def max_drawdown(self) -> float:
        """Maximum drawdown over the equity curve."""
        peak = self.equity_curve[0]
        max_dd = 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    def recovery_factor(self, total_pnl: float) -> float:
        max_dd_abs = self.peak * (self.max_drawdown() / 100.0)
        if max_dd_abs <= 0:
            return float("inf") if total_pnl > 0 else 0.0
        return total_pnl / max_dd_abs
