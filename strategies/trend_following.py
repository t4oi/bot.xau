"""Trend-following strategy: EMA cross + ADX filter + pullback entry."""
from __future__ import annotations
import math
from typing import List

from config.constants import SignalDirection
from data.base import Candle
from indicators.trend import ema, adx, supertrend
from indicators.momentum import rsi
from .base import Strategy, StrategyResult


class TrendFollowingStrategy(Strategy):
    name = "trend_following"
    description = "EMA trend filter with ADX strength confirmation and pullback entry."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 60:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        ema200 = ema(closes, 200) if len(closes) >= 200 else [float("nan")] * len(closes)
        adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)
        rsi_vals = rsi(closes, 14)
        st_line, st_dir = supertrend(highs, lows, closes, 10, 3.0)

        last = len(closes) - 1
        e20, e50, e200 = ema20[last], ema50[last], ema200[last]
        adx_last = adx_vals[last] if not math.isnan(adx_vals[last]) else 0
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50
        st_d = st_dir[last]

        result.raw_indicators = {
            "ema20": e20, "ema50": e50, "ema200": e200,
            "adx": adx_last, "rsi": rsi_last, "supertrend_dir": st_d,
        }

        trend_up = not math.isnan(e20) and not math.isnan(e50) and e20 > e50
        trend_down = not math.isnan(e20) and not math.isnan(e50) and e20 < e50
        strong_trend = adx_last >= 25

        # Bullish trend + pullback to EMA20 + RSI not overbought
        if trend_up and strong_trend and rsi_last < 70:
            if not math.isnan(e200) and e50 > e200:
                confidence = min(90, 55 + (adx_last - 25) * 1.5 + (10 if st_d == 1 else 0))
                result.votes.append(self.vote_buy(
                    confidence,
                    reasons=[f"EMA20>EMA50>EMA200", f"ADX={adx_last:.1f}",
                             f"RSI={rsi_last:.1f}", "Supertrend bullish" if st_d == 1 else ""],
                    timeframe=timeframe,
                ))
        elif trend_down and strong_trend and rsi_last > 30:
            if not math.isnan(e200) and e50 < e200:
                confidence = min(90, 55 + (adx_last - 25) * 1.5 + (10 if st_d == -1 else 0))
                result.votes.append(self.vote_sell(
                    confidence,
                    reasons=[f"EMA20<EMA50<EMA200", f"ADX={adx_last:.1f}",
                             f"RSI={rsi_last:.1f}", "Supertrend bearish" if st_d == -1 else ""],
                    timeframe=timeframe,
                ))
        else:
            result.votes.append(self.vote_neutral(
                reasons=[f"ADX={adx_last:.1f} trend weak" if not strong_trend else "choppy"],
                timeframe=timeframe,
            ))
        return result
