"""Fibonacci & pivot-point helpers."""
from __future__ import annotations
from typing import Dict, List

from ..core.utils import round_price


RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
EXTENSION_RATIOS = [1.0, 1.272, 1.618, 2.0, 2.618, 3.618, 4.236]


def fibonacci_retracement(swing_high: float, swing_low: float, direction: str) -> Dict[str, float]:
    """Retracement levels between swing high and swing low."""
    diff = swing_high - swing_low
    if direction.upper() in ("BUY", "LONG", "BULLISH"):
        # Retracement of an up-move: levels below high
        return {f"{r:.3f}": round_price(swing_high - diff * r) for r in RATIOS}
    return {f"{r:.3f}": round_price(swing_low + diff * r) for r in RATIOS}


def fibonacci_extension(swing_high: float, swing_low: float, direction: str) -> Dict[str, float]:
    """Extension (projection) levels beyond the swing."""
    diff = swing_high - swing_low
    if direction.upper() in ("BUY", "LONG", "BULLISH"):
        return {f"{r:.3f}": round_price(swing_high + diff * (r - 1.0)) for r in EXTENSION_RATIOS}
    return {f"{r:.3f}": round_price(swing_low - diff * (r - 1.0)) for r in EXTENSION_RATIOS}


def find_swing_points(highs: List[float], lows: List[float], lookback: int = 10) -> Dict[str, float]:
    """Find recent swing high and swing low."""
    if not highs or not lows:
        return {"swing_high": 0.0, "swing_low": 0.0}
    h_slice = highs[-lookback:]
    l_slice = lows[-lookback:]
    return {
        "swing_high": max(h_slice),
        "swing_low": min(l_slice),
    }


def nearest_fib_level(price: float, levels: Dict[str, float]) -> Dict[str, float]:
    """Return the nearest Fibonacci level to the current price."""
    if not levels:
        return {"ratio": "0.000", "price": price, "distance": 0.0}
    best_ratio, best_price, best_dist = "0.000", price, float("inf")
    for ratio, lvl in levels.items():
        dist = abs(price - lvl)
        if dist < best_dist:
            best_ratio, best_price, best_dist = ratio, lvl, dist
    return {"ratio": best_ratio, "price": best_price, "distance": round(best_dist, 2)}


def pivot_points_full(high: float, low: float, close: float, method: str = "classic") -> Dict[str, float]:
    """Full pivot point set (R3..S3) for a given method."""
    from ..core.utils import pivot_points
    return pivot_points(high, low, close, method)


def pivot_methods() -> List[str]:
    return ["classic", "woodie", "camarilla", "fibonacci"]
