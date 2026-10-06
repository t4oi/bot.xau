"""Market regime detection — trending vs ranging vs volatile vs quiet."""
from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple

from data.base import Candle
from indicators.trend import adx, ema
from indicators.volatility import average_true_range, bollinger_bands, bollinger_bandwidth


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    QUIET = "QUIET"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeResult:
    regime: MarketRegime
    adx: float
    trend_strength: float
    volatility: float
    bb_width: float
    ema_alignment: int
    confidence: float


class RegimeDetector:
    """Detects current market regime using ADX, volatility, and EMA alignment."""

    def __init__(self, lookback: int = 50):
        self.lookback = lookback

    def detect(self, candles: List[Candle]) -> RegimeResult:
        if len(candles) < 60:
            return RegimeResult(MarketRegime.UNKNOWN, 0, 0, 0, 0, 0, 0)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)
        atr = average_true_range(highs, lows, closes, 14)
        bb_mid, bb_up, bb_lo, _ = bollinger_bands(closes, 20, 2.0)
        bw = bollinger_bandwidth(bb_up, bb_lo, bb_mid)

        e20 = ema(closes, 20)[-1]
        e50 = ema(closes, 50)[-1]
        e200 = ema(closes, 200)[-1] if len(closes) >= 200 else e50

        def safe(v):
            return 0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v

        adx_last = safe(adx_vals[-1])
        atr_last = safe(atr[-1])
        bw_last = safe(bw[-1])
        price = closes[-1]

        # EMA alignment: +3 (bullish stack), -3 (bearish stack), 0 mixed
        alignment = 0
        if not math.isnan(e20) and not math.isnan(e50):
            alignment += 1 if e20 > e50 else -1
        if not math.isnan(e50) and not math.isnan(e200):
            alignment += 1 if e50 > e200 else -1
        if price > e20 if not math.isnan(e20) else False:
            alignment += 1
        elif price < e20 if not math.isnan(e20) else False:
            alignment -= 1

        atr_pct = atr_last / price * 100 if price > 0 else 0

        # Determine regime
        if adx_last >= 25 and alignment >= 2:
            regime = MarketRegime.TRENDING_UP
            confidence = min(95, 50 + (adx_last - 25) * 2)
        elif adx_last >= 25 and alignment <= -2:
            regime = MarketRegime.TRENDING_DOWN
            confidence = min(95, 50 + (adx_last - 25) * 2)
        elif atr_pct > 1.0 or bw_last > 8:
            regime = MarketRegime.VOLATILE
            confidence = 60
        elif adx_last < 20 and bw_last < 4:
            regime = MarketRegime.RANGING
            confidence = 65
        elif atr_pct < 0.3:
            regime = MarketRegime.QUIET
            confidence = 55
        else:
            regime = MarketRegime.UNKNOWN
            confidence = 30

        return RegimeResult(
            regime=regime, adx=round(adx_last, 1),
            trend_strength=round(adx_last, 1),
            volatility=round(atr_pct, 3),
            bb_width=round(bw_last, 2),
            ema_alignment=alignment,
            confidence=round(confidence, 1),
        )

    def regime_history(self, candles: List[Candle], window: int = 20) -> List[str]:
        """Detect regime over rolling windows for analysis."""
        regimes = []
        for i in range(self.lookback, len(candles), window):
            r = self.detect(candles[:i + 1])
            regimes.append(r.regime.value)
        return regimes

    def regime_stats(self, candles: List[Candle]) -> Dict[str, float]:
        history = self.regime_history(candles)
        total = len(history) or 1
        return {r: round(history.count(r) / total * 100, 1) for r in set(history)}
