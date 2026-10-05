"""Ichimoku Kinko Hyo strategy."""
from __future__ import annotations
import math
from typing import List

from ..data.base import Candle
from ..indicators.trend import ichimoku_cloud
from .base import Strategy, StrategyResult


class IchimokuStrategy(Strategy):
    name = "ichimoku"
    description = "Ichimoku cloud: price vs cloud, Tenkan/Kijun cross, Chikou confirmation."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 60:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        ichi = ichimoku_cloud(highs, lows, closes, 9, 26, 52)
        last = len(closes) - 1
        price = closes[last]

        tenkan = ichi["tenkan"][last] if not math.isnan(ichi["tenkan"][last]) else price
        kijun = ichi["kijun"][last] if not math.isnan(ichi["kijun"][last]) else price
        senkou_a = ichi["senkou_a"][last] if not math.isnan(ichi["senkou_a"][last]) else price
        senkou_b = ichi["senkou_b"][last] if not math.isnan(ichi["senkou_b"][last]) else price

        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)
        bullish_cloud = senkou_a > senkou_b

        result.raw_indicators = {"tenkan": tenkan, "kijun": kijun,
                                 "cloud_top": cloud_top, "cloud_bottom": cloud_bottom,
                                 "bullish_cloud": bullish_cloud}

        score = 0
        reasons: List[str] = []
        if price > cloud_top:
            score += 25
            reasons.append("Price above cloud")
        elif price < cloud_bottom:
            score -= 25
            reasons.append("Price below cloud")
        if tenkan > kijun:
            score += 20
            reasons.append("Tenkan>Kijun")
        elif tenkan < kijun:
            score -= 20
            reasons.append("Tenkan<Kijun")
        if bullish_cloud:
            score += 15
            reasons.append("Bullish cloud (green)")
        else:
            score -= 15
            reasons.append("Bearish cloud (red)")
        if price > tenkan:
            score += 10
        else:
            score -= 10

        if score >= 40:
            result.votes.append(self.vote_buy(min(88, 50 + score), reasons=reasons, timeframe=timeframe))
        elif score <= -40:
            result.votes.append(self.vote_sell(min(88, 50 + abs(score)), reasons=reasons, timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=[f"Score={score} mixed"], timeframe=timeframe))
        return result
