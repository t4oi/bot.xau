"""Shared utility helpers used across the whole bot."""
from __future__ import annotations
import datetime as dt
import functools
import math
import time
from typing import Any, Callable, Iterable, Iterator, List, Optional, TypeVar

from core.exceptions import BotError
from config.constants import SYMBOL_DIGITS, HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------
def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert anything to float without raising."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def midpoint(a: float, b: float) -> float:
    return (a + b) / 2.0


def round_to_digits(value: float, digits: int = SYMBOL_DIGITS) -> float:
    return round(value, digits)


def round_price(value: float) -> float:
    """Round a price to the symbol's pip precision."""
    return round_to_digits(value, SYMBOL_DIGITS)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0


def is_near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_iso() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc(ts: str) -> Optional[dt.datetime]:
    """Parse common timestamp formats into aware UTC datetime."""
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = dt.datetime.strptime(ts, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            continue
    return None


def minutes_since(ts: dt.datetime) -> float:
    return (now_utc() - ts).total_seconds() / 60.0


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def format_price(value: float, digits: int = SYMBOL_DIGITS) -> str:
    return f"{value:,.{digits}f}"


def format_pct(value: float, digits: int = 2) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}%"


def format_usd(value: float) -> str:
    return f"${value:,.2f}"


def format_lot(value: float) -> str:
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Iteration helpers
# ---------------------------------------------------------------------------
def chunks(seq: List[T], size: int) -> Iterator[List[T]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def moving_average(values: List[float], period: int) -> List[float]:
    """Simple moving average; shorter output padded with None at start."""
    result: List[float] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            result.append(running / period)
        else:
            result.append(float("nan"))
    return result


def exponential_moving_average(values: List[float], period: int) -> List[float]:
    """Standard EMA with SMA seed."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema = [float("nan")] * len(values)
    if len(values) < period:
        return ema
    seed = sum(values[:period]) / period
    ema[period - 1] = seed
    for i in range(period, len(values)):
        ema[i] = values[i] * k + ema[i - 1] * (1 - k)
    return ema


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


# ---------------------------------------------------------------------------
# Retry decorator / helper
# ---------------------------------------------------------------------------
def retry_call(
    func: Callable[..., T],
    *args: Any,
    retries: int = HTTP_MAX_RETRIES,
    backoff: float = HTTP_BACKOFF_FACTOR,
    exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> T:
    """Call func with exponential backoff retry."""
    last_exc: Optional[BaseException] = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == retries - 1:
                break
            time.sleep(backoff * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def retry(
    retries: int = HTTP_MAX_RETRIES,
    backoff: float = HTTP_BACKOFF_FACTOR,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator version of retry_call."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return retry_call(func, *args, retries=retries, backoff=backoff,
                              exceptions=exceptions, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Math / stats
# ---------------------------------------------------------------------------
def std_dev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def fibonacci_levels(high: float, low: float, direction: str) -> dict:
    """Return Fibonacci retracement/extension levels for a swing."""
    diff = high - low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618]
    if direction.upper() == "BUY":
        return {f"{r:.3f}": round_price(high - diff * r) for r in ratios}
    return {f"{r:.3f}": round_price(low + diff * r) for r in ratios}


def pivot_points(high: float, low: float, close: float, method: str = "classic") -> dict:
    """Classic / Woodie / Camarilla / Fibonacci pivot points."""
    rng = high - low
    if method == "classic":
        pp = (high + low + close) / 3
        return {
            "R3": round_price(high + 2 * (pp - low)),
            "R2": round_price(pp + rng),
            "R1": round_price(2 * pp - low),
            "PP": round_price(pp),
            "S1": round_price(2 * pp - high),
            "S2": round_price(pp - rng),
            "S3": round_price(low - 2 * (high - pp)),
        }
    if method == "woodie":
        pp = (high + low + 2 * close) / 4
        return {
            "R2": round_price(pp + rng),
            "R1": round_price(2 * pp - low),
            "PP": round_price(pp),
            "S1": round_price(2 * pp - high),
            "S2": round_price(pp - rng),
        }
    if method == "camarilla":
        return {
            "R4": round_price(close + rng * 1.1 / 2),
            "R3": round_price(close + rng * 1.1 / 4),
            "R2": round_price(close + rng * 1.1 / 6),
            "R1": round_price(close + rng * 1.1 / 12),
            "S1": round_price(close - rng * 1.1 / 12),
            "S2": round_price(close - rng * 1.1 / 6),
            "S3": round_price(close - rng * 1.1 / 4),
            "S4": round_price(close - rng * 1.1 / 2),
        }
    # fibonacci
    pp = (high + low + close) / 3
    return {
        "R3": round_price(pp + rng * 1.0),
        "R2": round_price(pp + rng * 0.618),
        "R1": round_price(pp + rng * 0.382),
        "PP": round_price(pp),
        "S1": round_price(pp - rng * 0.382),
        "S2": round_price(pp - rng * 0.618),
        "S3": round_price(pp - rng * 1.0),
    }
