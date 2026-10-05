"""Volume-based indicators: OBV, VWAP, A/D, Volume Profile, Money Flow."""
from __future__ import annotations
import math
from typing import Dict, List, Tuple


def on_balance_volume(closes: List[float], volumes: List[float]) -> List[float]:
    """On-Balance Volume."""
    n = len(closes)
    out: List[float] = [0.0] * n
    running = 0.0
    for i in range(1, n):
        v = volumes[i] if i < len(volumes) else 0.0
        if closes[i] > closes[i - 1]:
            running += v
        elif closes[i] < closes[i - 1]:
            running -= v
        out[i] = running
    return out


def vwap(highs: List[float], lows: List[float], closes: List[float],
         volumes: List[float]) -> List[float]:
    """Volume Weighted Average Price (cumulative from series start)."""
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


def accumulation_distribution(highs: List[float], lows: List[float], closes: List[float],
                              volumes: List[float]) -> List[float]:
    """Accumulation/Distribution Line."""
    n = len(closes)
    out: List[float] = [0.0] * n
    running = 0.0
    for i in range(n):
        rng = highs[i] - lows[i]
        v = volumes[i] if i < len(volumes) else 0.0
        if rng > 0:
            mfm = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / rng
        else:
            mfm = 0.0
        running += mfm * v
        out[i] = running
    return out


def volume_profile(closes: List[float], volumes: List[float], bins: int = 20) -> Dict[str, float]:
    """Volume-by-price profile. Returns price levels with volume + POC."""
    if not closes or not volumes:
        return {}
    lo, hi = min(closes), max(closes)
    if hi == lo:
        return {"poc": closes[-1]}
    width = (hi - lo) / bins
    profile: Dict[int, float] = {}
    for price, vol in zip(closes, volumes):
        idx = min(bins - 1, int((price - lo) / width))
        profile[idx] = profile.get(idx, 0.0) + vol
    poc_idx = max(profile, key=profile.get) if profile else 0
    poc_price = lo + (poc_idx + 0.5) * width
    # Value area (70% of volume)
    sorted_by_vol = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(profile.values())
    cumulative = 0.0
    value_bins = set()
    for idx, vol in sorted_by_vol:
        if cumulative >= total * 0.7:
            break
        cumulative += vol
        value_bins.add(idx)
    va_low = lo + min(value_bins) * width if value_bins else lo
    va_high = lo + (max(value_bins) + 1) * width if value_bins else hi
    return {
        "poc": round(poc_price, 2),
        "value_area_low": round(va_low, 2),
        "value_area_high": round(va_high, 2),
        "total_volume": total,
        "bins": {f"{lo + (i + 0.5) * width:.2f}": v for i, v in profile.items()},
    }


def money_flow(highs: List[float], lows: List[float], closes: List[float],
               volumes: List[float], period: int = 14) -> Tuple[List[float], str]:
    """Simplified money flow + interpretation."""
    from .momentum import mfi
    mfi_vals = mfi(highs, lows, closes, volumes, period)
    last = mfi_vals[-1] if mfi_vals and not math.isnan(mfi_vals[-1]) else 50.0
    if last >= 80:
        state = "overbought"
    elif last <= 20:
        state = "oversold"
    elif last >= 50:
        state = "accumulation"
    else:
        state = "distribution"
    return mfi_vals, state


def volume_spike(volumes: List[float], period: int = 20, mult: float = 2.0) -> bool:
    """True if latest volume is mult x the average."""
    if len(volumes) < period + 1:
        return False
    avg = sum(volumes[-period - 1:-1]) / period
    return avg > 0 and volumes[-1] > avg * mult
