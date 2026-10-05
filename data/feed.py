"""FeedManager — orchestrates multi-timeframe data fetching with caching."""
from __future__ import annotations
import time
from typing import Dict, List, Optional

from config.settings import get_settings
from core.logging_config import get_logger
from data.base import Candle, DataSource, Tick
from data.biquote import BiQuoteDataSource
from data.cache import DataCache
from data.storage import CandleStore

logger = get_logger("data.feed")


class FeedManager:
    """High-level facade over the data layer with caching + persistence."""

    def __init__(
        self,
        source: Optional[DataSource] = None,
        cache: Optional[DataCache] = None,
        store: Optional[CandleStore] = None,
        symbol: Optional[str] = None,
    ):
        settings = get_settings()
        self.symbol = symbol or settings.trading_symbol
        self.source = source or BiQuoteDataSource(
            base_url=settings.biquote_base_url,
            timeout=settings.http_timeout_seconds,
        )
        self.cache = cache or DataCache(default_ttl=5.0)
        self.store = store or CandleStore()
        self._last_fetch: Dict[str, float] = {}

    # ------------------------------------------------------------------
    def tick(self, force_refresh: bool = False) -> Optional[Tick]:
        if force_refresh:
            self.cache.invalidate(f"tick:{self.symbol}")
        return self.cache.get_or_compute(
            f"tick:{self.symbol}",
            lambda: self.source.get_tick(self.symbol),
            ttl=5.0,
        )

    def candles(self, interval: str, limit: int = 500, persist: bool = True) -> List[Candle]:
        key = f"ohlc:{self.symbol}:{interval}:{limit}"
        now = time.time()
        last = self._last_fetch.get(interval, 0)
        if now - last < 3.0:
            cached = self.cache.get(key)
            if cached:
                return cached

        candles = self.source.get_ohlc(self.symbol, interval, limit)
        if candles:
            self._last_fetch[interval] = now
            self.cache.set(key, candles, ttl=10.0)
            if persist:
                try:
                    self.store.append(self.symbol, interval, candles[-50:])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Persistence failed: %s", exc)
        return candles

    def multi_timeframe(
        self, intervals: List[str], limit: int = 500
    ) -> Dict[str, List[Candle]]:
        result: Dict[str, List[Candle]] = {}
        for tf in intervals:
            result[tf] = self.candles(tf, limit)
        return result

    def close_series(self, interval: str, limit: int = 500) -> List[float]:
        return [c.close for c in self.candles(interval, limit)]

    def health(self) -> dict:
        return {
            "source": self.source.name,
            "healthy": self.source.health_check(),
            "symbol": self.symbol,
            "cache_entries": len(self.cache),
        }

    def warm_up(self, intervals: List[str], limit: int = 500) -> None:
        """Pre-fetch all timeframes to warm caches before a scan."""
        logger.info("Warming up feed for %s on %d timeframes...", self.symbol, len(intervals))
        self.multi_timeframe(intervals, limit)
        logger.info("Warm-up complete.")
