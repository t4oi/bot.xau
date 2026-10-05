"""Slippage & commission models for realistic backtesting."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import random


@dataclass
class SlippageModel:
    """Models realistic execution costs."""

    slippage_pct: float = 0.0005      # 0.05% typical
    commission_per_lot: float = 0.0   # USD per lot
    spread_fixed: float = 0.20        # fixed spread in price units
    spread_volatility_mult: float = 1.5
    seed: Optional[int] = None

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def estimate_fill_price(self, intended_price: float, side: str, volatility: float = 0.0) -> float:
        """Apply slippage + spread to intended entry price."""
        dynamic_spread = self.spread_fixed + volatility * 0.1 * self.spread_volatility_mult
        slippage = intended_price * self.slippage_pct * (0.5 + self._rng.random())
        if side.upper() == "BUY":
            return intended_price + dynamic_spread / 2 + slippage
        return intended_price - dynamic_spread / 2 - slippage

    def commission_cost(self, lot_size: float) -> float:
        return self.commission_per_lot * lot_size

    def total_cost(self, intended_price: float, side: str, lot_size: float,
                   volatility: float = 0.0) -> dict:
        fill = self.estimate_fill_price(intended_price, side, volatility)
        slip = abs(fill - intended_price)
        comm = self.commission_cost(lot_size)
        slip_cost = slip * lot_size * 100.0
        return {
            "fill_price": round(fill, 2),
            "slippage_price": round(slip, 4),
            "slippage_cost_usd": round(slip_cost, 2),
            "commission_usd": round(comm, 2),
            "total_cost_usd": round(slip_cost + comm, 2),
        }


class SpreadForecaster:
    """Predicts spread based on session & volatility."""

    SESSION_SPREADS = {
        "ASIA": 0.15, "LONDON": 0.25, "NEW_YORK": 0.30,
        "OVERLAP_LN_NY": 0.35, "PACIFIC": 0.12,
    }

    @classmethod
    def forecast(cls, session: str, atr: float) -> float:
        base = cls.SESSION_SPREADS.get(session, 0.20)
        return round(base + atr * 0.02, 3)
