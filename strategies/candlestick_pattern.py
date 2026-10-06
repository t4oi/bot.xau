"""Candlestick Pattern Strategy — trades based on Japanese candlestick patterns.
Detects 15+ patterns (Doji, Hammer, Shooting Star, Engulfing, Harami, Piercing,
Dark Cloud Cover, Morning/Evening Star, Three White Soldiers/Black Crows, Marubozu)
and generates signals when multiple bullish/bearish patterns align.
"""
from __future__ import annotations
from typing import List

from config.constants import SignalDirection
from data.base import Candle
from indicators.candlestick import scan_candlestick_patterns, candlestick_net_score
from indicators.volatility import average_true_range
from strategies.base import Strategy, StrategyResult


class CandlestickPatternStrategy(Strategy):
    """Trade purely on Japanese candlestick pattern recognition."""

    name = "candlestick_patterns"
    description = "Entry based on Japanese candlestick pattern recognition (15+ patterns)."
    default_timeframes = ["5m", "15m", "1h", "4h"]

    # Pattern weights (multiplier on top of base scores)
    STRONG_PATTERNS = {
        "morning_star", "evening_star", "three_white_soldiers", "three_black_crows",
        "bullish_engulfing", "bearish_engulfing", "piercing_pattern", "dark_cloud_cover",
    }

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 5:
            result.votes.append(self.vote_neutral(reasons=["Not enough candles"], timeframe=timeframe))
            return result

        patterns = scan_candlestick_patterns(candles)
        net = candlestick_net_score(candles)

        # Count strong vs weak patterns
        strong_bull = sum(1 for p in patterns if p in self.STRONG_PATTERNS and patterns[p] > 0)
        strong_bear = sum(1 for p in patterns if p in self.STRONG_PATTERNS and patterns[p] < 0)
        total_patterns = len(patterns)

        result.raw_indicators = {
            "patterns_detected": list(patterns.keys()),
            "net_score": net,
            "strong_bullish": strong_bull,
            "strong_bearish": strong_bear,
        }

        # ATR filter — avoid signals in extremely low volatility
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        atr = average_true_range(highs, lows, closes, 14)[-1]
        atr_pct = atr / closes[-1] * 100 if closes[-1] and atr == atr else 0

        bullish_patterns = [p for p, s in patterns.items() if s > 0]
        bearish_patterns = [p for p, s in patterns.items() if s < 0]

        # Confidence scales with pattern count & strength
        if net >= 3 and atr_pct > 0.05:
            conf = min(90, 50 + abs(net) * 5 + strong_bull * 10)
            result.votes.append(self.vote_buy(
                conf,
                reasons=[f"Bullish patterns: {', '.join(bullish_patterns)}",
                         f"Net score +{net}",
                         f"{strong_bull} strong reversal pattern(s)"],
                timeframe=timeframe,
            ))
        elif net <= -3 and atr_pct > 0.05:
            conf = min(90, 50 + abs(net) * 5 + strong_bear * 10)
            result.votes.append(self.vote_sell(
                conf,
                reasons=[f"Bearish patterns: {', '.join(bearish_patterns)}",
                         f"Net score {net}",
                         f"{strong_bear} strong reversal pattern(s)"],
                timeframe=timeframe,
            ))
        elif total_patterns > 0:
            # Weak signal — low confidence, contributes to confluence
            if net > 0:
                result.votes.append(self.vote_buy(40, reasons=[f"Mild bullish: {', '.join(bullish_patterns)}"], timeframe=timeframe))
            elif net < 0:
                result.votes.append(self.vote_sell(40, reasons=[f"Mild bearish: {', '.join(bearish_patterns)}"], timeframe=timeframe))
            else:
                result.votes.append(self.vote_neutral(reasons=["Mixed candlestick patterns"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No candlestick pattern detected"], timeframe=timeframe))

        return result
