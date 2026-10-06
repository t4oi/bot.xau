"""Extra strategy library — 6 additional strategies: Keltner, VWAP bounce,
EMA ribbon, ADX filter, Heikin Ashi, Triple screen."""
from __future__ import annotations
import math
from typing import List

from config.constants import SignalDirection
from data.base import Candle
from indicators.trend import ema, supertrend
from indicators.momentum import rsi, macd, stochastic
from indicators.volatility import keltner_channels, average_true_range, bollinger_bands
from indicators.volume import vwap, volume_spike
from .base import Strategy, StrategyResult


class KeltnerBounceStrategy(Strategy):
    name = "keltner_bounce"
    description = "Bounce off Keltner channel extremes with RSI confirmation."
    default_timeframes = ["5m", "15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 40:
            return result
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        mid, upper, lower = keltner_channels(highs, lows, closes, 20, 10, 2.0)
        rsi_vals = rsi(closes, 14)
        last = len(closes) - 1
        price = closes[last]
        lo = lower[last] if not math.isnan(lower[last]) else price
        up = upper[last] if not math.isnan(upper[last]) else price
        rsi_last = rsi_vals[last] if not math.isnan(rsi_vals[last]) else 50

        if price <= lo and rsi_last < 35:
            result.votes.append(self.vote_buy(58, reasons=["Bounce off Keltner lower", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
        elif price >= up and rsi_last > 65:
            result.votes.append(self.vote_sell(58, reasons=["Reject Keltner upper", f"RSI={rsi_last:.1f}"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["Inside Keltner channel"], timeframe=timeframe))
        return result


class VWAPBounceStrategy(Strategy):
    name = "vwap_bounce"
    description = "Trend continuation with pullback to VWAP."
    default_timeframes = ["5m", "15m"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        vols = [c.volume for c in candles]
        vwap_line = vwap(highs, lows, closes, vols)
        e20 = ema(closes, 20)
        last = len(closes) - 1
        price = closes[last]
        v = vwap_line[last] if not math.isnan(vwap_line[last]) else price
        e = e20[last] if not math.isnan(e20[last]) else price

        if price > e and e > v and price <= v * 1.002:
            result.votes.append(self.vote_buy(57, reasons=["Pullback to VWAP in uptrend"], timeframe=timeframe))
        elif price < e and e < v and price >= v * 0.998:
            result.votes.append(self.vote_sell(57, reasons=["Pullback to VWAP in downtrend"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["No VWAP pullback"], timeframe=timeframe))
        return result


class EMARibbonStrategy(Strategy):
    name = "ema_ribbon"
    description = "EMA ribbon (8/14/21/50) alignment for trend entries."
    default_timeframes = ["15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 60:
            return result
        closes = [c.close for c in candles]
        e8 = ema(closes, 8)[-1]
        e14 = ema(closes, 14)[-1]
        e21 = ema(closes, 21)[-1]
        e50 = ema(closes, 50)[-1]
        price = closes[-1]
        vals = [e8, e14, e21, e50]
        if any(math.isnan(v) for v in vals):
            result.votes.append(self.vote_neutral(reasons=["Warmup"], timeframe=timeframe))
            return result
        bullish_aligned = e8 > e14 > e21 > e50 and price > e8
        bearish_aligned = e8 < e14 < e21 < e50 and price < e8
        if bullish_aligned:
            result.votes.append(self.vote_buy(62, reasons=["EMA ribbon bullish stack"], timeframe=timeframe))
        elif bearish_aligned:
            result.votes.append(self.vote_sell(62, reasons=["EMA ribbon bearish stack"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["EMA ribbon mixed"], timeframe=timeframe))
        return result


class HeikinAshiStrategy(Strategy):
    name = "heikin_ashi"
    description = "Heikin Ashi trend candles — trade with strong HA candles."
    default_timeframes = ["15m", "1h", "4h"]

    @staticmethod
    def _heikin_ashi(candles: List[Candle]) -> List[tuple]:
        ha = []
        for i, c in enumerate(candles):
            if i == 0:
                ha_open = (c.open + c.close) / 2
            else:
                ha_open = (ha[i-1][0] + ha[i-1][3]) / 2
            ha_close = (c.open + c.high + c.low + c.close) / 4
            ha_high = max(c.high, ha_open, ha_close)
            ha_low = min(c.low, ha_open, ha_close)
            ha.append((ha_open, ha_high, ha_low, ha_close))
        return ha

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 10:
            return result
        ha = self._heikin_ashi(candles)
        last = ha[-1]
        prev = ha[-2]
        body = last[3] - last[0]
        prev_body = prev[3] - prev[0]
        # Strong bullish HA candle (no lower wick) after bearish
        lower_wick = last[0] - last[2] if body > 0 else last[3] - last[2]
        upper_wick = last[1] - last[3] if body > 0 else last[1] - last[0]
        if body > 0 and lower_wick < abs(body) * 0.3 and prev_body <= 0:
            result.votes.append(self.vote_buy(55, reasons=["Strong bullish Heikin Ashi reversal"], timeframe=timeframe))
        elif body < 0 and upper_wick < abs(body) * 0.3 and prev_body >= 0:
            result.votes.append(self.vote_sell(55, reasons=["Strong bearish Heikin Ashi reversal"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["HA trend continuing"], timeframe=timeframe))
        return result


class TripleScreenStrategy(Strategy):
    name = "triple_screen"
    description = "Elder's Triple Screen: trend (higher TF), momentum (mid TF), entry (lower TF)."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 60:
            return result
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        # Screen 1: trend via EMA50 slope + MACD histogram
        e50 = ema(closes, 50)
        macd_line, signal_line, hist = macd(closes)
        trend_up = e50[-1] > e50[-6] if len(e50) >= 6 and not math.isnan(e50[-1]) else False
        trend_down = e50[-1] < e50[-6] if len(e50) >= 6 and not math.isnan(e50[-1]) else False
        # Screen 2: momentum oscillator (stochastic)
        k, d = stochastic(highs, lows, closes, 14, 3, 3)
        k_last = k[-1] if not math.isnan(k[-1]) else 50
        # Screen 3: entry via trailing buy/sell
        atr = average_true_range(highs, lows, closes, 14)[-1]
        atr = 0 if math.isnan(atr) else atr

        if trend_up and k_last < 40 and hist[-1] > hist[-2] if not math.isnan(hist[-1]) else False:
            result.votes.append(self.vote_buy(60, reasons=["Triple screen bullish", f"Stoch={k_last:.0f}"], timeframe=timeframe))
        elif trend_down and k_last > 60 and hist[-1] < hist[-2] if not math.isnan(hist[-1]) else False:
            result.votes.append(self.vote_sell(60, reasons=["Triple screen bearish", f"Stoch={k_last:.0f}"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_neutral(reasons=["Triple screen no setup"], timeframe=timeframe))
        return result


class SupertrendStrategy(Strategy):
    name = "supertrend_cross"
    description = "Supertrend flips as entry signals with ATR filter."
    default_timeframes = ["15m", "1h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        st_line, st_dir = supertrend(highs, lows, closes, 10, 3.0)
        last_dir = st_dir[-1]
        prev_dir = st_dir[-2] if len(st_dir) >= 2 else last_dir
        if last_dir == 1.0 and prev_dir == -1.0:
            result.votes.append(self.vote_buy(56, reasons=["Supertrend flip bullish"], timeframe=timeframe))
        elif last_dir == -1.0 and prev_dir == 1.0:
            result.votes.append(self.vote_sell(56, reasons=["Supertrend flip bearish"], timeframe=timeframe))
        elif last_dir == 1.0:
            result.votes.append(self.vote_buy(40, reasons=["Supertrend bullish trend"], timeframe=timeframe))
        else:
            result.votes.append(self.vote_sell(40, reasons=["Supertrend bearish trend"], timeframe=timeframe))
        return result
