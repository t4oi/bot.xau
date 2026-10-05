"""Trend indicators: SMA, EMA, WMA, HMA, Ichimoku, ADX, Parabolic SAR, Supertrend."""
from __future__ import annotations
import math
from typing import Dict, List, Tuple

from .base import IndicatorResult


# ---------------------------------------------------------------------------
def sma(values: List[float], period: int) -> List[float]:
    """Simple Moving Average."""
    if period <= 0 or not values:
        return []
    result: List[float] = [float("nan")] * len(values)
    if len(values) < period:
        return result
    running = sum(values[:period])
    result[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        result[i] = running / period
    return result


def ema(values: List[float], period: int) -> List[float]:
    """Exponential Moving Average (SMA-seeded)."""
    if period <= 0 or not values:
        return []
    result: List[float] = [float("nan")] * len(values)
    if len(values) < period:
        return result
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1.0 - k)
    return result


def wma(values: List[float], period: int) -> List[float]:
    """Weighted Moving Average (linear weights)."""
    if period <= 0 or not values:
        return []
    result: List[float] = [float("nan")] * len(values)
    weights = list(range(1, period + 1))
    wsum = sum(weights)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        result[i] = sum(v * w for v, w in zip(window, weights)) / wsum
    return result


def hma(values: List[float], period: int) -> List[float]:
    """Hull Moving Average."""
    if period <= 0 or not values:
        return []
    half = max(1, period // 2)
    sqrt_p = max(1, int(math.sqrt(period)))
    wma_half = wma(values, half)
    wma_full = wma(values, period)
    raw = [
        2 * h - f if not (math.isnan(h) or math.isnan(f)) else float("nan")
        for h, f in zip(wma_half, wma_full)
    ]
    return wma(raw, sqrt_p)


def ema_series(values: List[float], period: int) -> List[float]:
    return ema(values, period)


# ---------------------------------------------------------------------------
def ichimoku_cloud(
    highs: List[float], lows: List[float], closes: List[float],
    tenkan: int = 9, kijun: int = 26, senkou: int = 52,
) -> Dict[str, List[float]]:
    """Ichimoku Kinko Hyo. Returns tenkan, kijun, senkou_a, senkou_b, chikou."""
    n = len(closes)
    def donchian_mid(period: int, offset: int = 0) -> List[float]:
        out: List[float] = [float("nan")] * n
        for i in range(period - 1 + offset, n):
            start = i - period + 1 - offset
            end = i - offset + 1
            hh = max(highs[start:end])
            ll = min(lows[start:end])
            out[i] = (hh + ll) / 2.0
        return out

    tenkan_sen = donchian_mid(tenkan)
    kijun_sen = donchian_mid(kijun)
    senkou_b = donchian_mid(senkou)

    senkou_a: List[float] = [float("nan")] * (n + kijun)
    for i in range(n):
        if not (math.isnan(tenkan_sen[i]) or math.isnan(kijun_sen[i])):
            senkou_a[i + kijun] = (tenkan_sen[i] + kijun_sen[i]) / 2.0
    senkou_b_padded = [float("nan")] * kijun + senkou_b

    chikou = closes[:] + [float("nan")] * kijun

    length = max(len(senkou_a), len(senkou_b_padded), len(chikou))
    def pad(arr: List[float]) -> List[float]:
        return arr + [float("nan")] * (length - len(arr))

    return {
        "tenkan": pad(tenkan_sen),
        "kijun": pad(kijun_sen),
        "senkou_a": pad(senkou_a[:n]),
        "senkou_b": pad(senkou_b_padded[:n]),
        "chikou": pad(chikou[:n]),
    }


# ---------------------------------------------------------------------------
def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[List[float], List[float], List[float]]:
    """Average Directional Index. Returns (adx, +di, -di)."""
    n = len(closes)
    if n < period + 1:
        nan = [float("nan")] * n
        return nan, nan, nan

    plus_dm: List[float] = [0.0] * n
    minus_dm: List[float] = [0.0] * n
    tr: List[float] = [0.0] * n

    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    def wilder_smooth(data: List[float], p: int) -> List[float]:
        out = [float("nan")] * n
        if n <= p:
            return out
        out[p] = sum(data[1:p + 1])
        for i in range(p + 1, n):
            out[i] = out[i - 1] - (out[i - 1] / p) + data[i]
        return out

    atr_s = wilder_smooth(tr, period)
    plus_dm_s = wilder_smooth(plus_dm, period)
    minus_dm_s = wilder_smooth(minus_dm, period)

    plus_di: List[float] = [float("nan")] * n
    minus_di: List[float] = [float("nan")] * n
    dx: List[float] = [float("nan")] * n
    for i in range(period, n):
        if atr_s[i] and not math.isnan(atr_s[i]) and atr_s[i] > 0:
            plus_di[i] = 100.0 * plus_dm_s[i] / atr_s[i]
            minus_di[i] = 100.0 * minus_dm_s[i] / atr_s[i]
            denom = plus_di[i] + minus_di[i]
            if denom > 0:
                dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / denom

    adx_out = wilder_smooth([0.0 if math.isnan(x) else x for x in dx], period)
    for i in range(period * 2):
        if i < n:
            adx_out[i] = float("nan")
    return adx_out, plus_di, minus_di


# ---------------------------------------------------------------------------
def parabolic_sar(
    highs: List[float], lows: List[float],
    af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2,
) -> List[float]:
    """Parabolic SAR (Wilder)."""
    n = len(highs)
    if n < 2:
        return [float("nan")] * n
    sar: List[float] = [float("nan")] * n
    sar[0] = lows[0]
    long_trend = True
    af = af_start
    ep = highs[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if math.isnan(prev_sar):
            prev_sar = lows[i - 1]
        if long_trend:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = min(sar[i], lows[i - 1], lows[i - 2] if i >= 2 else lows[i - 1])
            if highs[i] > ep:
                ep = highs[i]
                af = min(af + af_step, af_max)
            if lows[i] < sar[i]:
                long_trend = False
                sar[i] = ep
                ep = lows[i]
                af = af_start
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = max(sar[i], highs[i - 1], highs[i - 2] if i >= 2 else highs[i - 1])
            if lows[i] < ep:
                ep = lows[i]
                af = min(af + af_step, af_max)
            if highs[i] > sar[i]:
                long_trend = True
                sar[i] = ep
                ep = highs[i]
                af = af_start
    return sar


# ---------------------------------------------------------------------------
def supertrend(
    highs: List[float], lows: List[float], closes: List[float],
    period: int = 10, multiplier: float = 3.0,
) -> Tuple[List[float], List[float]]:
    """Supertrend indicator. Returns (supertrend_line, direction)."""
    from .volatility import average_true_range
    atr_vals = average_true_range(highs, lows, closes, period)
    n = len(closes)
    st: List[float] = [float("nan")] * n
    direction: List[float] = [1.0] * n  # 1 = up (bullish), -1 = down
    if n < period + 1:
        return st, direction

    final_upper = 0.0
    final_lower = 0.0
    for i in range(period, n):
        a = atr_vals[i]
        if math.isnan(a):
            continue
        hl2 = (highs[i] + lows[i]) / 2.0
        basic_upper = hl2 + multiplier * a
        basic_lower = hl2 - multiplier * a

        if i == period or math.isnan(st[i - 1]):
            final_upper = basic_upper
            final_lower = basic_lower
            direction[i] = 1.0
        else:
            final_upper = (basic_upper if basic_upper < final_upper or closes[i - 1] > final_upper
                          else final_upper)
            final_lower = (basic_lower if basic_lower > final_lower or closes[i - 1] < final_lower
                          else final_lower)

            if direction[i - 1] == 1.0 and closes[i] < final_lower:
                direction[i] = -1.0
            elif direction[i - 1] == -1.0 and closes[i] > final_upper:
                direction[i] = 1.0
            else:
                direction[i] = direction[i - 1]

        st[i] = final_upper if direction[i] == -1.0 else final_lower
    return st, direction


# ---------------------------------------------------------------------------
def vwap_anchor(highs: List[float], lows: List[float], closes: List[float],
                volumes: List[float]) -> List[float]:
    """Anchored VWAP from start of series."""
    n = len(closes)
    out: List[float] = [float("nan")] * n
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(n):
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        v = volumes[i] if i < len(volumes) else 0.0
        cum_pv += typical * v
        cum_v += v
        if cum_v > 0:
            out[i] = cum_pv / cum_v
    return out
