"""Breakout strategy: Donchian channel breakout with volume confirmation."""
from __future__ import annotations
import math
from typing import List

from data.base import Candle
from indicators.volatility import donchian_channels, average_true_range
from indicators.volume import volume_spike
from .base import Strategy, StrategyResult


class BreakoutStrategy(Strategy):
    name = "breakout"
    description = "Donchian channel breakout with ATR and volume confirmation."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        upper, lower, mid = donchian_channels(highs, lows, 20)
        atr = average_true_range(highs, lows, closes, 14)

        last = len(closes) - 1
        price = closes[last]
        up_last = upper[last] if not math.isnan(upper[last]) else price
        low_last = lower[last] if not math.isnan(lower[last]) else price
        atr_last = atr[last] if not math.isnan(atr[last]) else 0
        spike = volume_spike(volumes, 20, 1.8) if volumes else False

        # Squeeze before breakout (narrow range)
        prev_highs = highs[-10:-1]
        prev_lows = lows[-10:-1]
        squeeze = (max(prev_highs) - min(prev_lows)) < (atr_last * 3) if atr_last > 0 else False

        result.raw_indicators = {"donchian_upper": up_last, "donchian_lower": low_last,
                                 "atr": atr_last, "volume_spike": spike, "squeeze": squeeze}

        if price > up_last and atr_last > 0:
            confidence = 60 + (15 if spike else 0) + (10 if squeeze else 0)
            result.votes.append(self.vote_buy(
                min(90, confidence),
                reasons=["Break above Donchian upper"] +
                        (["Volume spike"] if spike else []) +
                        (["Squeeze breakout"] if squeeze else []),
                timeframe=timeframe,
            ))
        elif price < low_last and atr_last > 0:
            confidence = 60 + (15 if spike else 0) + (10 if squeeze else 0)
            result.votes.append(self.vote_sell(
                min(90, confidence),
                reasons=["Break below Donchian lower"] +
                        (["Volume spike"] if spike else []) +
                        (["Squeeze breakout"] if squeeze else []),
                timeframe=timeframe,
            ))
        else:
            result.votes.append(self.vote_neutral(
                reasons=["Inside Donchian channel"],
                timeframe=timeframe,
            ))
        return result
