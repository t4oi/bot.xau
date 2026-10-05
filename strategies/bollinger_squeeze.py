"""Bollinger Squeeze strategy — volatility contraction then expansion."""
from __future__ import annotations
import math
from typing import List

from ..data.base import Candle
from ..indicators.volatility import bollinger_bands, bollinger_bandwidth, keltner_channels
from ..indicators.momentum import rsi
from .base import Strategy, StrategyResult


class BollingerSqueezeStrategy(Strategy):
    name = "bollinger_squeeze"
    description = "BB inside Keltner = squeeze; breakout direction traded."
    default_timeframes = ["15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 40:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        bb_mid, bb_upper, bb_lower, _ = bollinger_bands(closes, 20, 2.0)
        kc_mid, kc_upper, kc_lower = keltner_channels(highs, lows, closes, 20, 10, 1.5)
        bandwidth = bollinger_bandwidth(bb_upper, bb_lower, bb_mid)
        rsi_vals = rsi(closes, 14)

        last = len(closes) - 1
        price = closes[last]
        bb_up = bb_upper[last] if not math.isnan(bb_upper[last]) else price
        bb_lo = bb_lower[last] if not math.isnan(bb_lower[last]) else price
        kc_up = kc_upper[last] if not math.isnan(kc_upper[last]) else price
        kc_lo = kc_lower[last] if not math.isnan(kc_lower[last]) else price
        bw_last = bandwidth[last] if not math.isnan(bandwidth[last]) else 0
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50

        # Squeeze: BB inside Keltner
        in_squeeze = bb_up < kc_up and bb_lo > kc_lo and bw_last > 0

        result.raw_indicators = {"in_squeeze": in_squeeze, "bandwidth": bw_last, "rsi": rsi_last}

        if in_squeeze:
            result.votes.append(self.vote_neutral(
                reasons=[f"Squeeze active (BW={bw_last:.2f}) — wait for breakout"],
                timeframe=timeframe,
            ))
        else:
            # Check if just broke out of squeeze
            prev_in_squeeze = False
            for i in range(max(0, last - 5), last):
                if not math.isnan(bandwidth[i]) and bandwidth[i] < bw_last * 0.8:
                    prev_in_squeeze = True
                    break
            if prev_in_squeeze:
                if price > bb_up and rsi_last > 50:
                    result.votes.append(self.vote_buy(
                        70, reasons=["Squeeze breakout up", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
                elif price < bb_lo and rsi_last < 50:
                    result.votes.append(self.vote_sell(
                        70, reasons=["Squeeze breakout down", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
                else:
                    result.votes.append(self.vote_neutral(reasons=["Squeeze released, direction unclear"], timeframe=timeframe))
            else:
                result.votes.append(self.vote_neutral(reasons=["No squeeze condition"], timeframe=timeframe))
        return result
