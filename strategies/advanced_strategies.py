"""Additional advanced strategies — Elliott Wave, Harmonic, Smart Money, Divergence."""
from __future__ import annotations
import math
from typing import List

from config.constants import SignalDirection
from data.base import Candle
from indicators.momentum import rsi, macd, rsi_divergence
from indicators.trend import ema
from .base import Strategy, StrategyResult


class MomentumDivergenceStrategy(Strategy):
    name = "momentum_divergence"
    description = "Trade RSI/MACD divergence against price."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 40:
            return result
        closes = [c.close for c in candles]
        rsi_vals = rsi(closes, 14)
        div = rsi_divergence(closes, rsi_vals, lookback=20)
        macd_line, signal_line, hist = macd(closes)

        last_rsi = rsi_vals[-1] if not math.isnan(rsi_vals[-1]) else 50
        result.raw_indicators = {"divergence": div, "rsi": last_rsi}

        if div == "bullish" and last_rsi < 45:
            result.votes.append(self.vote_buy(
                65, reasons=["Bullish RSI divergence", f"RSI={last_rsi:.1f}"], timeframe=timeframe))
        elif div == "bearish" and last_rsi > 55:
            result.votes.append(self.vote_sell(
                65, reasons=["Bearish RSI divergence", f"RSI={last_rsi:.1f}"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No divergence"], timeframe=timeframe))
        return result


class SmartMoneyConceptsStrategy(Strategy):
    name = "smart_money"
    description = "Order blocks, fair value gaps, liquidity sweeps."
    default_timeframes = ["15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 20:
            return result
        last = candles[-1]
        prev = candles[-2]
        prev2 = candles[-3]

        # Fair Value Gap: 3-candle imbalance
        fvg_bullish = prev2.high < candles[-1].low  # gap up
        fvg_bearish = prev2.low > candles[-1].high  # gap down

        # Liquidity sweep: wick beyond recent high/low then close back
        lookback_high = max(c.high for c in candles[-20:-1])
        lookback_low = min(c.low for c in candles[-20:-1])
        sweep_high = last.high > lookback_high and last.close < lookback_high
        sweep_low = last.low < lookback_low and last.close > lookback_low

        result.raw_indicators = {"fvg_bullish": fvg_bullish, "fvg_bearish": fvg_bearish,
                                 "sweep_high": sweep_high, "sweep_low": sweep_low}

        if sweep_low or fvg_bullish:
            reasons = (["Liquidity sweep below low then close back"] if sweep_low else []) + \
                      (["Bullish FVG"] if fvg_bullish else [])
            result.votes.append(self.vote_buy(60, reasons=reasons, timeframe=timeframe))
        elif sweep_high or fvg_bearish:
            reasons = (["Liquidity sweep above high then close back"] if sweep_high else []) + \
                      (["Bearish FVG"] if fvg_bearish else [])
            result.votes.append(self.vote_sell(60, reasons=reasons, timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No SMC setup"], timeframe=timeframe))
        return result


class HarmonicPatternStrategy(Strategy):
    name = "harmonic"
    description = "Detect Gartley/Butterfly/Bat harmonic patterns (simplified)."
    default_timeframes = ["1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result
        # Simplified: find 4 swing points X-A-B-C and check ratios
        closes = [c.close for c in candles]
        # Look for recent swing structure
        swing_indices = self._find_swings(candles, 5)
        if len(swing_indices) < 4:
            result.votes.append(self.vote_neutral(reasons=["Insufficient swings"], timeframe=timeframe))
            return result

        X, A, B, C = swing_indices[-4:]
        XA = abs(closes[A] - closes[X])
        AB = abs(closes[B] - closes[A])
        BC = abs(closes[C] - closes[B])
        if XA == 0:
            result.votes.append(self.vote_neutral(reasons=["Invalid pattern"], timeframe=timeframe))
            return result

        ab_ratio = AB / XA
        bc_ratio = BC / AB if AB > 0 else 0

        # Gartley: AB ~ 0.618 XA, BC ~ 0.382-0.886 AB
        is_gartley = 0.5 < ab_ratio < 0.75 and 0.3 < bc_ratio < 1.0
        result.raw_indicators = {"ab_ratio": round(ab_ratio, 3), "bc_ratio": round(bc_ratio, 3),
                                 "gartley": is_gartley}

        if is_gartley and closes[C] > closes[B]:
            result.votes.append(self.vote_buy(58, reasons=["Potential Gartley completion (bullish)"], timeframe=timeframe))
        elif is_gartley and closes[C] < closes[B]:
            result.votes.append(self.vote_sell(58, reasons=["Potential Gartley completion (bearish)"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No harmonic pattern"], timeframe=timeframe))
        return result

    @staticmethod
    def _find_swings(candles: List[Candle], lookaround: int = 5) -> List[int]:
        swings = []
        for i in range(lookaround, len(candles) - lookaround):
            h = candles[i].high
            l = candles[i].low
            is_high = all(h >= candles[j].high for j in range(i - lookaround, i + lookaround + 1) if j != i)
            is_low = all(l <= candles[j].low for j in range(i - lookaround, i + lookaround + 1) if j != i)
            if is_high or is_low:
                swings.append(i)
        return swings


class VolumeSpreadStrategy(Strategy):
    name = "volume_spread"
    description = "Volume spread analysis (Wyckoff method simplified)."
    default_timeframes = ["15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 25:
            return result
        last = candles[-1]
        avg_vol = sum(c.volume for c in candles[-20:-1]) / 19
        vol_ratio = last.volume / avg_vol if avg_vol > 0 else 1
        range_ratio = last.range / (sum(c.range for c in candles[-20:-1]) / 19 or 1)

        # No demand: up candle on low volume -> bearish
        # No supply: down candle on low volume -> bullish
        no_demand = last.is_bullish and vol_ratio < 0.7 and range_ratio < 0.8
        no_supply = last.is_bearish and vol_ratio < 0.7 and range_ratio < 0.8
        climactic = vol_ratio > 2.0

        result.raw_indicators = {"vol_ratio": round(vol_ratio, 2), "range_ratio": round(range_ratio, 2),
                                 "no_demand": no_demand, "no_supply": no_supply, "climactic": climactic}

        if no_supply:
            result.votes.append(self.vote_buy(55, reasons=["No supply (down bar, low volume)"], timeframe=timeframe))
        elif no_demand:
            result.votes.append(self.vote_sell(55, reasons=["No demand (up bar, low volume)"], timeframe=timeframe))
        elif climactic and last.is_bearish:
            result.votes.append(self.vote_buy(50, reasons=["Selling climax — potential reversal"], timeframe=timeframe))
        elif climactic and last.is_bullish:
            result.votes.append(self.vote_sell(50, reasons=["Buying climax — potential reversal"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["Normal volume action"], timeframe=timeframe))
        return result
