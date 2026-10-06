"""Take-profit / stop-loss calculator — ATR-based + structure-based."""
from __future__ import annotations
import math
from typing import Dict, List, Optional

from config.constants import SignalDirection
from core.utils import round_price
from data.base import Candle
from indicators.volatility import average_true_range
from indicators.fibonacci import fibonacci_extension, find_swing_points


class TpSlCalculator:
    """Computes entry, stop loss and multiple take-profit levels."""

    def __init__(self, atr_period: int = 14, sl_multiplier: float = 1.5,
                 tp_multipliers: Optional[List[float]] = None):
        self.atr_period = atr_period
        self.sl_multiplier = sl_multiplier
        self.tp_multipliers = tp_multipliers or [1.5, 3.0, 5.0]

    def compute(self, candles: List[Candle], direction: SignalDirection,
                current_price: float, num_tps: int = 3) -> Dict:
        """Return {entry, stop_loss, take_profits: [...], risk_reward, atr}."""
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]

        atr_vals = average_true_range(highs, lows, closes, self.atr_period)
        atr = atr_vals[-1] if atr_vals and not math.isnan(atr_vals[-1]) else current_price * 0.005

        entry = round_price(current_price)

        # Stop loss: ATR-based, adjusted by recent swing
        swings = find_swing_points(highs, lows, lookback=20)
        if direction == SignalDirection.BUY:
            sl_atr = entry - self.sl_multiplier * atr
            sl_structure = swings["swing_low"] * 0.999
            stop_loss = round_price(max(sl_atr, sl_structure))
            risk = entry - stop_loss
        else:
            sl_atr = entry + self.sl_multiplier * atr
            sl_structure = swings["swing_high"] * 1.001
            stop_loss = round_price(min(sl_atr, sl_structure))
            risk = stop_loss - entry

        if risk <= 0:
            risk = self.sl_multiplier * atr

        take_profits: List[float] = []
        for i, mult in enumerate(self.tp_multipliers[:num_tps]):
            if direction == SignalDirection.BUY:
                tp = round_price(entry + risk * mult)
            else:
                tp = round_price(entry - risk * mult)
            take_profits.append(tp)

        rr = (take_profits[0] - entry) / risk if direction == SignalDirection.BUY and risk > 0 else \
             (entry - take_profits[0]) / risk if risk > 0 else 0.0

        # Fibonacci confluence for TP1
        fib_ext = fibonacci_extension(
            swings["swing_high"], swings["swing_low"],
            "BUY" if direction == SignalDirection.BUY else "SELL",
        )

        return {
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "risk_per_unit": round(risk, 2),
            "atr": round(atr, 2),
            "risk_reward_tp1": round(rr, 2),
            "fibonacci_extensions": fib_ext,
            "sl_method": "ATR+swing",
        }

    def breakeven_price(self, entry: float, stop_loss: float, direction: SignalDirection) -> float:
        """Price at which to move SL to breakeven (e.g. after 1R)."""
        risk = abs(entry - stop_loss)
        if direction == SignalDirection.BUY:
            return round_price(entry + risk)
        return round_price(entry - risk)
