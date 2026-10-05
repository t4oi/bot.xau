"""MACD + RSI confluence strategy."""
from __future__ import annotations
import math
from typing import List

from ..data.base import Candle
from ..indicators.momentum import macd, rsi, macd_cross
from .base import Strategy, StrategyResult


class MacdRsiStrategy(Strategy):
    name = "macd_rsi"
    description = "MACD crossover confirmed by RSI trend direction."
    default_timeframes = ["5m", "15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 40:
            return result

        closes = [c.close for c in candles]
        macd_line, signal_line, hist = macd(closes, 12, 26, 9)
        rsi_vals = rsi(closes, 14)
        cross = macd_cross(macd_line, signal_line)

        last = len(closes) - 1
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50
        hist_last = hist[last] if not math.isnan(hist[last]) else 0
        hist_prev = hist[last - 1] if not math.isnan(hist[last - 1]) else 0

        result.raw_indicators = {"rsi": rsi_last, "macd_hist": hist_last, "cross": cross}

        if cross == "bullish_cross" and rsi_last > 45 and rsi_last < 75:
            confidence = min(85, 60 + (rsi_last - 45))
            result.votes.append(self.vote_buy(
                confidence,
                reasons=["MACD bullish cross", f"RSI={rsi_last:.1f} confirms", "Hist rising"],
                timeframe=timeframe,
            ))
        elif cross == "bearish_cross" and rsi_last < 55 and rsi_last > 25:
            confidence = min(85, 60 + (55 - rsi_last))
            result.votes.append(self.vote_sell(
                confidence,
                reasons=["MACD bearish cross", f"RSI={rsi_last:.1f} confirms", "Hist falling"],
                timeframe=timeframe,
            ))
        elif hist_last > 0 and hist_last > hist_prev and rsi_last > 50:
            result.votes.append(self.vote_buy(45, reasons=["MACD momentum up", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
        elif hist_last < 0 and hist_last < hist_prev and rsi_last < 50:
            result.votes.append(self.vote_sell(45, reasons=["MACD momentum down", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No MACD/RSI setup"], timeframe=timeframe))
        return result
