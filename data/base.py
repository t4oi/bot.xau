"""Abstract data-source interface + domain models for market data."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Tick:
    """A single real-time price tick."""
    symbol: str
    bid: float
    ask: float
    mid: float
    spread: float
    high: float = 0.0
    low: float = 0.0
    day_diff_pct: float = 0.0
    timestamp: str = ""
    market_state: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Candle:
    """OHLCV bar. `time` is an ISO8601 string of the bar open time."""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    tick_volume: float = 0.0
    is_open: bool = False

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Alias used by some modules
Bar = Candle


class DataSource(ABC):
    """Abstract base class every market-data provider must implement."""

    name: str = "abstract"

    @abstractmethod
    def get_tick(self, symbol: str) -> Optional[Tick]:
        """Return the latest real-time tick for a symbol."""

    @abstractmethod
    def get_ohlc(self, symbol: str, interval: str, limit: int = 1000) -> List[Candle]:
        """Return closed candles, oldest -> newest."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable and responding."""

    def get_close_series(self, symbol: str, interval: str, limit: int = 1000) -> List[float]:
        """Convenience: close prices only."""
        return [c.close for c in self.get_ohlc(symbol, interval, limit)]

    def get_multi_timeframe(
        self, symbol: str, intervals: List[str], limit: int = 1000
    ) -> Dict[str, List[Candle]]:
        """Fetch candles for several timeframes in one call."""
        return {tf: self.get_ohlc(symbol, tf, limit) for tf in intervals}
