"""Signal validators — additional sanity checks before delivery."""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple

from ..config.constants import SignalDirection, GOLD_MAX_SPREAD
from ..core.logging_config import get_logger
from ..data.base import Candle, Tick
from ..signal.generator import TradingSignal

logger = get_logger("signal.validators")


class SignalValidator:
    """Runs final validation checks on a generated signal."""

    def __init__(self, max_spread: float = GOLD_MAX_SPREAD,
                 min_atr_pct: float = 0.05, max_atr_pct: float = 2.0):
        self.max_spread = max_spread
        self.min_atr_pct = min_atr_pct
        self.max_atr_pct = max_atr_pct

    def validate(self, signal: TradingSignal, candles: List[Candle],
                 tick: Optional[Tick] = None) -> Tuple[bool, List[str]]:
        """Return (is_valid, list_of_issues)."""
        issues: List[str] = []

        # 1. Entry price sanity
        if signal.entry <= 0:
            issues.append("Invalid entry price")
        if signal.stop_loss <= 0:
            issues.append("Invalid stop loss")
        if not signal.take_profits or any(tp <= 0 for tp in signal.take_profits):
            issues.append("Invalid take profit")

        # 2. SL on correct side
        if signal.is_buy and signal.stop_loss >= signal.entry:
            issues.append("SL above entry for BUY")
        if signal.is_sell and signal.stop_loss <= signal.entry:
            issues.append("SL below entry for SELL")

        # 3. TP on correct side
        if signal.is_buy and any(tp <= signal.entry for tp in signal.take_profits):
            issues.append("TP below entry for BUY")
        if signal.is_sell and any(tp >= signal.entry for tp in signal.take_profits):
            issues.append("TP above entry for SELL")

        # 4. Risk/reward sanity
        if signal.risk_reward < 1.0:
            issues.append(f"R:R too low ({signal.risk_reward:.2f})")

        # 5. Spread check
        if tick and tick.spread > self.max_spread:
            issues.append(f"Spread too high ({tick.spread:.2f})")

        # 6. ATR sanity (not too quiet, not too volatile)
        if signal.atr > 0 and signal.entry > 0:
            atr_pct = signal.atr / signal.entry * 100
            if atr_pct < self.min_atr_pct:
                issues.append(f"ATR too low ({atr_pct:.3f}%) — market too quiet")
            elif atr_pct > self.max_atr_pct:
                issues.append(f"ATR too high ({atr_pct:.3f}%) — extreme volatility")

        # 7. Confluence minimum
        if signal.confluence_pct < 50:
            issues.append(f"Confluence too low ({signal.confluence_pct:.1f}%)")

        # 8. Entry within recent range (not absurd)
        if candles:
            recent_high = max(c.high for c in candles[-20:])
            recent_low = min(c.low for c in candles[-20:])
            margin = (recent_high - recent_low) * 0.5
            if signal.entry > recent_high + margin or signal.entry < recent_low - margin:
                issues.append("Entry far outside recent range")

        if issues:
            logger.info("Signal %s invalid: %s", signal.id, "; ".join(issues))
        return (len(issues) == 0), issues
