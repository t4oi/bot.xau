"""Momentum oscillators: RSI, MACD, Stochastic, CCI, Williams %R, ROC, MFI, AO."""
from __future__ import annotations
import math
from typing import List, Tuple

from .trend import ema, sma


# ---------------------------------------------------------------------------
def rsi(values: List[float], period: int = 14) -> List[float]:
    """Relative Strength Index (Wilder smoothing)."""
    n = len(values)
    if n < period + 1:
        return [float("nan")] * n
    gains: List[float] = [0.0] * n
    losses: List[float] = [0.0] * n
    for i in range(1, n):
        change = values[i] - values[i - 1]
        gains[i] = change if change > 0 else 0.0
        losses[i] = -change if change < 0 else 0.0

    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period
    out: List[float] = [float("nan")] * n
    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def rsi_divergence(values: List[float], rsi_vals: List[float], lookback: int = 20) -> str:
    """Detect bullish/bearish divergence. Returns 'bullish','bearish','none'."""
    n = len(values)
    if n < lookback + 5:
        return "none"
    price_low_idx = min(range(n - lookback, n), key=lambda i: values[i])
    price_high_idx = max(range(n - lookback, n), key=lambda i: values[i])
    rsi_at_low = rsi_vals[price_low_idx] if not math.isnan(rsi_vals[price_low_idx]) else 50
    rsi_at_high = rsi_vals[price_high_idx] if not math.isnan(rsi_vals[price_high_idx]) else 50
    current_rsi = rsi_vals[-1] if not math.isnan(rsi_vals[-1]) else 50
    if price_low_idx >= n - lookback // 2 and current_rsi > rsi_at_low + 5:
        return "bullish"
    if price_high_idx >= n - lookback // 2 and current_rsi < rsi_at_high - 5:
        return "bearish"
    return "none"


# ---------------------------------------------------------------------------
def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9
         ) -> Tuple[List[float], List[float], List[float]]:
    """MACD line, signal line, histogram."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [
        f - s if not (math.isnan(f) or math.isnan(s)) else float("nan")
        for f, s in zip(ema_fast, ema_slow)
    ]
    # Signal = EMA of macd_line (skip NaN prefix)
    valid_start = next((i for i, v in enumerate(macd_line) if not math.isnan(v)), 0)
    valid_slice = macd_line[valid_start:]
    signal_slice = ema(valid_slice, signal)
    signal_line = [float("nan")] * valid_start + signal_slice
    histogram = [
        m - s if not (math.isnan(m) or math.isnan(s)) else float("nan")
        for m, s in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, histogram


def macd_cross(macd_line: List[float], signal_line: List[float]) -> str:
    """Detect recent MACD crossover. Returns 'bullish_cross','bearish_cross','none'."""
    if len(macd_line) < 3:
        return "none"
    for i in range(len(macd_line) - 1, max(0, len(macd_line) - 4), -1):
        if math.isnan(macd_line[i]) or math.isnan(signal_line[i]):
            continue
        prev_m, prev_s = macd_line[i - 1], signal_line[i - 1]
        if math.isnan(prev_m) or math.isnan(prev_s):
            continue
        if prev_m <= prev_s and macd_line[i] > signal_line[i]:
            return "bullish_cross"
        if prev_m >= prev_s and macd_line[i] < signal_line[i]:
            return "bearish_cross"
    return "none"


# ---------------------------------------------------------------------------
def stochastic(highs: List[float], lows: List[float], closes: List[float],
               k_period: int = 14, d_period: int = 3, smooth: int = 3) -> Tuple[List[float], List[float]]:
    """Stochastic oscillator %K and %D."""
    n = len(closes)
    raw_k: List[float] = [float("nan")] * n
    for i in range(k_period - 1, n):
        hh = max(highs[i - k_period + 1:i + 1])
        ll = min(lows[i - k_period + 1:i + 1])
        if hh != ll:
            raw_k[i] = 100.0 * (closes[i] - ll) / (hh - ll)
        else:
            raw_k[i] = 50.0
    k_smooth = sma([0.0 if math.isnan(x) else x for x in raw_k], smooth)
    for i in range(smooth - 1):
        if i < n:
            k_smooth[i] = float("nan")
    d_line = sma([0.0 if math.isnan(x) else x for x in k_smooth], d_period)
    for i in range(d_period + smooth - 2):
        if i < n:
            d_line[i] = float("nan")
    return k_smooth, d_line


# ---------------------------------------------------------------------------
def cci(highs: List[float], lows: List[float], closes: List[float], period: int = 20) -> List[float]:
    """Commodity Channel Index."""
    n = len(closes)
    tp = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    out: List[float] = [float("nan")] * n
    for i in range(period - 1, n):
        window = tp[i - period + 1:i + 1]
        mean = sum(window) / period
        mean_dev = sum(abs(x - mean) for x in window) / period
        out[i] = (tp[i] - mean) / (0.015 * mean_dev) if mean_dev > 0 else 0.0
    return out


# ---------------------------------------------------------------------------
def williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Williams %R (range -100 to 0)."""
    n = len(closes)
    out: List[float] = [float("nan")] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        if hh != ll:
            out[i] = -100.0 * (hh - closes[i]) / (hh - ll)
    return out


# ---------------------------------------------------------------------------
def roc(values: List[float], period: int = 12) -> List[float]:
    """Rate of Change (%)."""
    n = len(values)
    out: List[float] = [float("nan")] * n
    for i in range(period, n):
        if values[i - period] != 0:
            out[i] = ((values[i] - values[i - period]) / values[i - period]) * 100.0
    return out


# ---------------------------------------------------------------------------
def mfi(highs: List[float], lows: List[float], closes: List[float],
        volumes: List[float], period: int = 14) -> List[float]:
    """Money Flow Index."""
    n = len(closes)
    tp = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    raw_mf = [tp[i] * (volumes[i] if i < len(volumes) else 0.0) for i in range(n)]
    positive: List[float] = [0.0] * n
    negative: List[float] = [0.0] * n
    for i in range(1, n):
        if tp[i] > tp[i - 1]:
            positive[i] = raw_mf[i]
        elif tp[i] < tp[i - 1]:
            negative[i] = raw_mf[i]
    out: List[float] = [float("nan")] * n
    for i in range(period, n):
        pos = sum(positive[i - period + 1:i + 1])
        neg = sum(negative[i - period + 1:i + 1])
        if neg == 0:
            out[i] = 100.0
        else:
            mr = pos / neg
            out[i] = 100.0 - (100.0 / (1.0 + mr))
    return out


# ---------------------------------------------------------------------------
def awesome_oscillator(highs: List[float], lows: List[float]) -> List[float]:
    """Awesome Oscillator (AO) = SMA5(median) - SMA34(median)."""
    median = [(h + l) / 2.0 for h, l in zip(highs, lows)]
    sma5 = sma(median, 5)
    sma34 = sma(median, 34)
    return [
        a - b if not (math.isnan(a) or math.isnan(b)) else float("nan")
        for a, b in zip(sma5, sma34)
    ]
