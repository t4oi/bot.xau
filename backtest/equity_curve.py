"""Equity curve tracker with drawdown analysis."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class EquityCurve:
    initial_balance: float
    points: List[Tuple[int, float]] = field(default_factory=list)  # (bar_index, equity)

    def __post_init__(self):
        if not self.points:
            self.points = [(0, self.initial_balance)]

    def add(self, bar_index: int, equity: float) -> None:
        self.points.append((bar_index, equity))

    @property
    def values(self) -> List[float]:
        return [p[1] for p in self.points]

    @property
    def final_equity(self) -> float:
        return self.points[-1][1] if self.points else self.initial_balance

    @property
    def peak(self) -> float:
        return max(p[1] for p in self.points) if self.points else self.initial_balance

    def max_drawdown_pct(self) -> float:
        peak = self.initial_balance
        max_dd = 0.0
        for _, eq in self.points:
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return round(max_dd, 2)

    def max_drawdown_usd(self) -> float:
        peak = self.initial_balance
        max_dd = 0.0
        for _, eq in self.points:
            peak = max(peak, eq)
            max_dd = max(max_dd, peak - eq)
        return round(max_dd, 2)

    def returns_pct(self) -> float:
        final = self.final_equity
        return round((final - self.initial_balance) / self.initial_balance * 100.0, 2)

    def to_dict(self) -> dict:
        return {
            "initial_balance": self.initial_balance,
            "final_equity": self.final_equity,
            "returns_pct": self.returns_pct(),
            "max_drawdown_pct": self.max_drawdown_pct(),
            "points": [{"bar": i, "equity": e} for i, e in self.points[-500:]],
        }
