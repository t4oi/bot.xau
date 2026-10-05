"""Volatility indicators: Bollinger, ATR, Keltner, Donchian, StdDev, Chandelier."""
from __future__ import annotations
import math
from typing import List, Tuple

from .trend import ema, sma


def standard_deviation(values: List[float], period: int) -> List[float]:
    """Rolling standard deviation (sample)."""
    n = len(values)
    out: List[float] = [float("nan")] * n
    for i in range(period - 1, n):
        window = values[i - period + 1:i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / (period - 1)
        out[i] = math.sqrt(var)
    return out


def bollinger_bands(values: List[float], period: int = 20, std_mult: float = 2.0
                    ) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Bollinger Bands: middle, upper, lower, %B."""
    middle = sma(values, period)
    sd = standard_deviation(values, period)
    upper = [m + std_mult * s if not (math.isnan(m) or math.isnan(s)) else float("nan")
             for m, s in zip(middle, sd)]
    lower = [m - std_mult * s if not (math.isnan(m) or math.isnan(s)) else float("nan")
             for m, s in zip(middle, sd)]
    pct_b = [
        (v - lo) / (up - lo) if not (math.isnan(v) or math.isnan(lo) or math.isnan(up)) and up != lo
        else float("nan")
        for v, lo, up in zip(values, lower, upper)
    ]
    return middle, upper, lower, pct_b


def bollinger_bandwidth(upper: List[float], lower: List[float], middle: List[float]) -> List[float]:
    return [
        (u - l) / m * 100.0 if not (math.isnan(u) or math.isnan(l) or math.isnan(m)) and m != 0
        else float("nan")
        for u, l, m in zip(upper, lower, middle)
    ]


def average_true_range(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Average True Range (Wilder smoothing)."""
    n = len(closes)
    if n < 2:
        return [float("nan")] * n
    tr: List[float] = [0.0] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    out: List[float] = [float("nan")] * n
    if n < period:
        return out
    out[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def keltner_channels(highs: List[float], lows: List[float], closes: List[float],
                     period: int = 20, atr_period: int = 10, mult: float = 2.0
                     ) -> Tuple[List[float], List[float], List[float]]:
    """Keltner Channels: middle (EMA), upper, lower."""
    middle = ema(closes, period)
    atr = average_true_range(highs, lows, closes, atr_period)
    upper = [m + mult * a if not (math.isnan(m) or math.isnan(a)) else float("nan")
             for m, a in zip(middle, atr)]
    lower = [m - mult * a if not (math.isnan(m) or math.isnan(a)) else float("nan")
             for m, a in zip(middle, atr)]
    return middle, upper, lower


def donchian_channels(highs: List[float], lows: List[float], period: int = 20
                      ) -> Tuple[List[float], List[float], List[float]]:
    """Donchian Channels: upper (highest high), lower (lowest low), midline."""
    n = len(highs)
    upper: List[float] = [float("nan")] * n
    lower: List[float] = [float("nan")] * n
    mid: List[float] = [float("nan")] * n
    for i in range(period - 1, n):
        upper[i] = max(highs[i - period + 1:i + 1])
        lower[i] = min(lows[i - period + 1:i + 1])
        mid[i] = (upper[i] + lower[i]) / 2.0
    return upper, lower, mid


def chandelier_exit(highs: List[float], lows: List[float], closes: List[float],
                    period: int = 22, mult: float = 3.0) -> Tuple[List[float], List[float]]:
    """Chandelier Exit long & short."""
    atr = average_true_range(highs, lows, closes, period)
    n = len(closes)
    long_exit: List[float] = [float("nan")] * n
    short_exit: List[float] = [float("nan")] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        if not math.isnan(atr[i]):
            long_exit[i] = hh - mult * atr[i]
            short_exit[i] = ll + mult * atr[i]
    return long_exit, short_exit


def volatility_ratio(highs: List[float], lows: List[float], closes: List[float], period: int = 10) -> List[float]:
    """Ratio of current ATR to longer-term ATR — detects expansion/contraction."""
    atr_short = average_true_range(highs, lows, closes, period)
    atr_long = average_true_range(highs, lows, closes, period * 3)
    return [
        s / l if not (math.isnan(s) or math.isnan(l)) and l > 0 else float("nan")
        for s, l in zip(atr_short, atr_long)
    ]
