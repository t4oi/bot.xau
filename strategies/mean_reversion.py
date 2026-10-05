"""Mean-reversion strategy: RSI extremes + Bollinger band touches + bounce."""
from __future__ import annotations
import math
from typing import List

from ..data.base import Candle
from ..indicators.momentum import rsi, stochastic
from ..indicators.volatility import bollinger_bands
from .base import Strategy, StrategyResult


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"
    description = "Trade reversals from oversold/overbought extremes at Bollinger bands."
    default_timeframes = ["5m", "15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 40:
            return result

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        rsi_vals = rsi(closes, 14)
        mid, upper, lower, pctb = bollinger_bands(closes, 20, 2.0)
        k, d = stochastic(highs, lows, closes, 14, 3, 3)

        last = len(closes) - 1
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50
        pctb_last = pctb[last] if not math.isnan(pctb[last]) else 0.5
        k_last = k[last] if not math.isnan(k[last]) else 50
        d_last = d[last] if not math.isnan(d[last]) else 50
        price = closes[last]
        lower_last = lower[last] if not math.isnan(lower[last]) else price
        upper_last = upper[last] if not math.isnan(upper[last]) else price

        result.raw_indicators = {"rsi": rsi_last, "%b": pctb_last, "stoch_k": k_last}

        # Oversold + touch lower band + stoch turning up
        if rsi_last < 30 and price <= lower_last * 1.001 and k_last < 25 and k_last >= d_last:
            confidence = min(85, 50 + (30 - rsi_last) * 1.5 + (25 - k_last))
            result.votes.append(self.vote_buy(
                confidence,
                reasons=[f"RSI oversold {rsi_last:.1f}", "Touch lower BB",
                         f"Stoch K={k_last:.1f} turning up"],
                timeframe=timeframe,
            ))
        elif rsi_last > 70 and price >= upper_last * 0.999 and k_last > 75 and k_last <= d_last:
            confidence = min(85, 50 + (rsi_last - 70) * 1.5 + (k_last - 75))
            result.votes.append(self.vote_sell(
                confidence,
                reasons=[f"RSI overbought {rsi_last:.1f}", "Touch upper BB",
                         f"Stoch K={k_last:.1f} turning down"],
                timeframe=timeframe,
            ))
        else:
            result.votes.append(self.vote_neutral(
                reasons=[f"RSI={rsi_last:.1f} in neutral zone"],
                timeframe=timeframe,
            ))
        return result
