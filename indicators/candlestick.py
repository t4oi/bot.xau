"""Candlestick pattern recognition (15+ classic patterns)."""
from __future__ import annotations
from typing import Dict, List, Optional

from data.base import Candle


def _body(c: Candle) -> float:
    return abs(c.close - c.open)


def _upper_wick(c: Candle) -> float:
    return c.high - max(c.open, c.close)


def _lower_wick(c: Candle) -> float:
    return min(c.open, c.close) - c.low


def _is_bullish(c: Candle) -> bool:
    return c.close >= c.open


def _is_bearish(c: Candle) -> bool:
    return c.close < c.open


# ---------------------------------------------------------------------------
def detect_doji(c: Candle, threshold: float = 0.1) -> bool:
    """Doji: body very small relative to range."""
    rng = c.range
    if rng <= 0:
        return False
    return _body(c) / rng < threshold


def detect_marubozu(c: Candle, threshold: float = 0.05) -> Optional[str]:
    """Marubozu: very small/no wicks. Returns 'bullish'/'bearish'/None."""
    rng = c.range
    if rng <= 0:
        return None
    if _upper_wick(c) / rng < threshold and _lower_wick(c) / rng < threshold:
        return "bullish" if _is_bullish(c) else "bearish"
    return None


def detect_hammer(c: Candle) -> bool:
    """Hammer: small body at top, long lower wick."""
    rng = c.range
    if rng <= 0:
        return False
    body = _body(c)
    lower = _lower_wick(c)
    upper = _upper_wick(c)
    return lower >= 2 * body and upper <= body * 0.5


def detect_shooting_star(c: Candle) -> bool:
    """Shooting star: small body at bottom, long upper wick."""
    rng = c.range
    if rng <= 0:
        return False
    body = _body(c)
    upper = _upper_wick(c)
    lower = _lower_wick(c)
    return upper >= 2 * body and lower <= body * 0.5


def detect_engulfing(prev: Candle, curr: Candle) -> Optional[str]:
    """Engulfing pattern. Returns 'bullish'/'bearish'/None."""
    if _is_bearish(prev) and _is_bullish(curr):
        if curr.open <= prev.close and curr.close >= prev.open:
            return "bullish"
    if _is_bullish(prev) and _is_bearish(curr):
        if curr.open >= prev.close and curr.close <= prev.open:
            return "bearish"
    return None


def detect_harami(prev: Candle, curr: Candle) -> Optional[str]:
    """Harami: small real body inside previous large body."""
    prev_body_high = max(prev.open, prev.close)
    prev_body_low = min(prev.open, prev.close)
    curr_body_high = max(curr.open, curr.close)
    curr_body_low = min(curr.open, curr.close)
    if curr_body_high < prev_body_high and curr_body_low > prev_body_low:
        if _is_bearish(prev) and _is_bullish(curr):
            return "bullish"
        if _is_bullish(prev) and _is_bearish(curr):
            return "bearish"
    return None


def detect_piercing_pattern(prev: Candle, curr: Candle) -> bool:
    """Piercing pattern: bullish reversal."""
    if not (_is_bearish(prev) and _is_bullish(curr)):
        return False
    midpoint_prev = (prev.open + prev.close) / 2.0
    return curr.open < prev.low and curr.close > midpoint_prev and curr.close < prev.open


def detect_dark_cloud_cover(prev: Candle, curr: Candle) -> bool:
    """Dark Cloud Cover: bearish reversal."""
    if not (_is_bullish(prev) and _is_bearish(curr)):
        return False
    midpoint_prev = (prev.open + prev.close) / 2.0
    return curr.open > prev.high and curr.close < midpoint_prev and curr.close > prev.close


def detect_morning_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    """Morning Star: bullish 3-candle reversal."""
    if not (_is_bearish(c1) and _is_bullish(c3)):
        return False
    if _body(c2) >= _body(c1) * 0.5:
        return False
    return c3.close > (c1.open + c1.close) / 2.0


def detect_evening_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    """Evening Star: bearish 3-candle reversal."""
    if not (_is_bullish(c1) and _is_bearish(c3)):
        return False
    if _body(c2) >= _body(c1) * 0.5:
        return False
    return c3.close < (c1.open + c1.close) / 2.0


def detect_three_white_soldiers(c1: Candle, c2: Candle, c3: Candle) -> bool:
    if not all(_is_bullish(c) for c in (c1, c2, c3)):
        return False
    return (c2.close > c1.close and c3.close > c2.close and
            c2.open > c1.open and c3.open > c2.open and
            _upper_wick(c3) < _body(c3) * 0.5)


def detect_three_black_crows(c1: Candle, c2: Candle, c3: Candle) -> bool:
    if not all(_is_bearish(c) for c in (c1, c2, c3)):
        return False
    return (c2.close < c1.close and c3.close < c2.close and
            c2.open < c1.open and c3.open < c2.open and
            _lower_wick(c3) < _body(c3) * 0.5)


# ---------------------------------------------------------------------------
PATTERN_SCORES: Dict[str, int] = {
    "bullish_engulfing": +25, "bearish_engulfing": -25,
    "bullish_harami": +15, "bearish_harami": -15,
    "hammer": +20, "shooting_star": -20,
    "piercing_pattern": +20, "dark_cloud_cover": -20,
    "morning_star": +30, "evening_star": -30,
    "three_white_soldiers": +30, "three_black_crows": -30,
    "doji": 0, "bullish_marubozu": +10, "bearish_marubozu": -10,
}


def scan_candlestick_patterns(candles: List[Candle]) -> Dict[str, int]:
    """Scan the last few candles for patterns. Returns {pattern_name: score}."""
    found: Dict[str, int] = {}
    if len(candles) < 3:
        return found
    last = candles[-1]
    prev = candles[-2]
    prev2 = candles[-3]

    if detect_doji(last):
        found["doji"] = PATTERN_SCORES["doji"]

    maru = detect_marubozu(last)
    if maru == "bullish":
        found["bullish_marubozu"] = PATTERN_SCORES["bullish_marubozu"]
    elif maru == "bearish":
        found["bearish_marubozu"] = PATTERN_SCORES["bearish_marubozu"]

    if detect_hammer(last) and _is_bullish(last):
        found["hammer"] = PATTERN_SCORES["hammer"]
    if detect_shooting_star(last) and _is_bearish(last):
        found["shooting_star"] = PATTERN_SCORES["shooting_star"]

    eng = detect_engulfing(prev, last)
    if eng == "bullish":
        found["bullish_engulfing"] = PATTERN_SCORES["bullish_engulfing"]
    elif eng == "bearish":
        found["bearish_engulfing"] = PATTERN_SCORES["bearish_engulfing"]

    har = detect_harami(prev, last)
    if har == "bullish":
        found["bullish_harami"] = PATTERN_SCORES["bullish_harami"]
    elif har == "bearish":
        found["bearish_harami"] = PATTERN_SCORES["bearish_harami"]

    if detect_piercing_pattern(prev, last):
        found["piercing_pattern"] = PATTERN_SCORES["piercing_pattern"]
    if detect_dark_cloud_cover(prev, last):
        found["dark_cloud_cover"] = PATTERN_SCORES["dark_cloud_cover"]

    if detect_morning_star(prev2, prev, last):
        found["morning_star"] = PATTERN_SCORES["morning_star"]
    if detect_evening_star(prev2, prev, last):
        found["evening_star"] = PATTERN_SCORES["evening_star"]

    if detect_three_white_soldiers(prev2, prev, last):
        found["three_white_soldiers"] = PATTERN_SCORES["three_white_soldiers"]
    if detect_three_black_crows(prev2, prev, last):
        found["three_black_crows"] = PATTERN_SCORES["three_black_crows"]

    return found


def candlestick_net_score(candles: List[Candle]) -> int:
    """Net bullish/bearish score from detected patterns."""
    return sum(scan_candlestick_patterns(candles).values())
