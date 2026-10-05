"""Extended core helpers — validators, math, time, data structures."""
from __future__ import annotations
import math
import re
from typing import Any, Dict, List, Optional, Tuple


# --- Validators ---
def validate_price(value: Any) -> Optional[float]:
    """Validate a price is a positive finite number."""
    try:
        v = float(value)
        if math.isfinite(v) and v > 0:
            return v
    except (TypeError, ValueError):
        pass
    return None


def validate_lot_size(value: Any, min_lot: float = 0.01, max_lot: float = 100.0) -> Optional[float]:
    try:
        v = float(value)
        if min_lot <= v <= max_lot:
            return round(v, 2)
    except (TypeError, ValueError):
        pass
    return None


def validate_telegram_token(token: str) -> bool:
    """Check Telegram bot token format: <digits>:<alphanumeric>."""
    return bool(re.match(r"^\d{6,12}:[A-Za-z0-9_-]{20,}$", token or ""))


def validate_chat_id(chat_id: str) -> bool:
    """Chat ID is numeric, optionally negative for groups."""
    try:
        cid = int(chat_id)
        return cid != 0
    except (TypeError, ValueError):
        return False


# --- Math helpers ---
def geometric_mean(values: List[float]) -> float:
    if not values or any(v <= 0 for v in values):
        return 0.0
    return math.exp(sum(math.log(v) for v in values) / len(values))


def harmonic_mean(values: List[float]) -> float:
    if not values or any(v <= 0 for v in values):
        return 0.0
    return len(values) / sum(1.0 / v for v in values)


def weighted_average(values: List[float], weights: List[float]) -> float:
    total_w = sum(weights)
    if total_w == 0:
        return 0.0
    return sum(v * w for v, w in zip(values, weights)) / total_w


def covariance(x: List[float], y: List[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    mx, my = sum(x[:n]) / n, sum(y[:n]) / n
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x[:n], y[:n])) / (n - 1)


def beta(asset: List[float], market: List[float]) -> float:
    cov = covariance(asset, market)
    var_market = covariance(market, market)
    return cov / var_market if var_market != 0 else 0.0


def sharpe_ratio(returns: List[float], risk_free: float = 0.0) -> float:
    if not returns:
        return 0.0
    excess = [r - risk_free for r in returns]
    mean = sum(excess) / len(excess)
    std = math.sqrt(sum((r - mean) ** 2 for r in excess) / len(excess))
    return mean / std if std > 0 else 0.0


def sortino_ratio(returns: List[float], risk_free: float = 0.0) -> float:
    if not returns:
        return 0.0
    excess = [r - risk_free for r in returns]
    mean = sum(excess) / len(excess)
    downside = [r for r in excess if r < 0]
    downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 0
    return mean / downside_std if downside_std > 0 else 0.0


def calmar_ratio(annual_return: float, max_drawdown_pct: float) -> float:
    if max_drawdown_pct <= 0:
        return 0.0
    return annual_return / max_drawdown_pct


def z_score(values: List[float], value: float) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
    return (value - mean) / std if std > 0 else 0.0


# --- Time helpers ---
def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def is_weekend(day_of_week: int) -> bool:
    return day_of_week >= 5  # Sat=5, Sun=6


def market_open_utc(hour: int, day_of_week: int) -> bool:
    """Gold market open approx: Monday 00:00 to Friday 22:00 UTC."""
    if is_weekend(day_of_week):
        return False
    if day_of_week == 4 and hour >= 22:  # Friday close
        return False
    return True


# --- Data structures ---
class RingBuffer:
    """Fixed-size circular buffer."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data: List[Any] = []
        self._index = 0

    def append(self, item: Any) -> None:
        if len(self._data) < self.capacity:
            self._data.append(item)
        else:
            self._data[self._index] = item
        self._index = (self._index + 1) % self.capacity

    def values(self) -> List[Any]:
        return self._data

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        self._data.clear()
        self._index = 0


class ExpiringCache:
    """Simple TTL cache with manual expiry."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        import time
        entry = self._store.get(key)
        if not entry:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        import time
        self._store[key] = (time.time(), value)

    def cleanup(self) -> int:
        import time
        expired = [k for k, (ts, _) in self._store.items() if time.time() - ts > self.ttl]
        for k in expired:
            del self._store[k]
        return len(expired)
