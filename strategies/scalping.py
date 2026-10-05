"""Scalping strategy: fast EMA + RSI + stochastic on lower timeframes."""
from __future__ import annotations
import math
from typing import List

from ..data.base import Candle
from ..indicators.trend import ema
from ..indicators.momentum import rsi, stochastic, macd
from .base import Strategy, StrategyResult


class ScalpingStrategy(Strategy):
    name = "scalping"
    description = "Fast scalp entries on M1/M5 using EMA stack + RSI + Stoch."
    default_timeframes = ["1m", "5m"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        e5 = ema(closes, 5)
        e13 = ema(closes, 13)
        rsi_vals = rsi(closes, 7)
        k, d = stochastic(highs, lows, closes, 9, 3, 3)
        macd_line, signal_line, hist = macd(closes, 12, 26, 9)

        last = len(closes) - 1
        price = closes[last]
        e5_last = e5[last] if not math.isnan(e5[last]) else price
        e13_last = e13[last] if not math.isnan(e13[last]) else price
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50
        k_last = k[last] if not math.isnan(k[last]) else 50
        d_last = d[last] if not math.isnan(d[last]) else 50
        hist_last = hist[last] if not math.isnan(hist[last]) else 0
        hist_prev = hist[last - 1] if not math.isnan(hist[last - 1]) else 0

        bullish = e5_last > e13_last and 35 < rsi_last < 65 and k_last > d_last and hist_last > hist_prev
        bearish = e5_last < e13_last and 35 < rsi_last < 65 and k_last < d_last and hist_last < hist_prev

        result.raw_indicators = {"ema5": e5_last, "ema13": e13_last,
                                 "rsi": rsi_last, "stoch_k": k_last, "macd_hist": hist_last}

        if bullish:
            result.votes.append(self.vote_buy(
                62,
                reasons=["EMA5>EMA13", f"RSI={rsi_last:.1f}", "Stoch cross up", "MACD hist rising"],
                timeframe=timeframe,
            ))
        elif bearish:
            result.votes.append(self.vote_sell(
                62,
                reasons=["EMA5<EMA13", f"RSI={rsi_last:.1f}", "Stoch cross down", "MACD hist falling"],
                timeframe=timeframe,
            ))
        else:
            result.votes.append(self.vote_neutral(reasons=["No scalp setup"], timeframe=timeframe))
        return result
