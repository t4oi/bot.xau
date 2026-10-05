"""
BiQuote.io data-source implementation.
Extracted from the original repository and hardened with retries,
circuit-breaker, caching and validation.
"""
from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from ..config.constants import (
    APP_NAME, APP_VERSION, DEFAULT_SYMBOL,
    HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR, RATE_LIMIT_SLEEP_SECONDS,
)
from ..core.exceptions import DataSourceError
from ..core.logging_config import get_logger
from ..core.utils import safe_float, midpoint, round_price
from .base import Candle, DataSource, Tick

logger = get_logger("data.biquote")


class BiQuoteDataSource(DataSource):
    """HTTP client using only the Python standard library (urllib)."""

    name = "biquote"

    def __init__(
        self,
        base_url: str = "https://biquote.io/api",
        timeout: int = 25,
        cache_ttl: float = 8.0,
        max_retries: int = HTTP_MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self._cache: Dict[str, tuple] = {}
        self._failure_count = 0
        self._circuit_open_until = 0.0
        self._last_success = 0.0

    # ------------------------------------------------------------------
    # Internal HTTP
    # ------------------------------------------------------------------
    def _circuit_ok(self) -> bool:
        if time.time() < self._circuit_open_until:
            return False
        return True

    def _open_circuit(self, seconds: int = 60) -> None:
        self._circuit_open_until = time.time() + seconds
        logger.warning("Circuit breaker OPEN for %ds after repeated failures", seconds)

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None, use_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        if not self._circuit_ok():
            raise DataSourceError("Circuit breaker open", provider=self.name)

        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        if use_cache and url in self._cache:
            ts, data = self._cache[url]
            if time.time() - ts < self.cache_ttl:
                return data

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": f"{APP_NAME}/{APP_VERSION}",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self._failure_count = 0
                    self._last_success = time.time()
                    if use_cache:
                        self._cache[url] = (time.time(), data)
                    return data
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    wait = int(exc.headers.get("Retry-After", RATE_LIMIT_SLEEP_SECONDS))
                    logger.warning("Rate limited (429). Sleeping %ds", wait)
                    time.sleep(wait)
                    continue
                if exc.code >= 500:
                    time.sleep(HTTP_BACKOFF_FACTOR * (attempt + 1))
                    continue
                logger.error("HTTP %s on %s", exc.code, url)
                break
            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning("URL error on %s (attempt %d): %s", url, attempt + 1, exc)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                last_error = exc
                logger.error("Invalid JSON from %s: %s", url, exc)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.error("Request error %s: %s", url, exc)
            time.sleep(HTTP_BACKOFF_FACTOR * (attempt + 1))

        self._failure_count += 1
        if self._failure_count >= 10:
            self._open_circuit(60)
        raise DataSourceError(
            f"Failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_tick(self, symbol: str = DEFAULT_SYMBOL) -> Optional[Tick]:
        try:
            data = self._get(f"{symbol}", use_cache=True)
        except DataSourceError:
            return None
        if not data:
            return None

        bid = safe_float(data.get("bid"))
        ask = safe_float(data.get("ask"))
        mid = safe_float(data.get("mid"))
        if mid <= 0 and bid > 0 and ask > 0:
            mid = midpoint(bid, ask)
        spread = safe_float(data.get("spread"))
        if spread <= 0 and bid > 0 and ask > 0:
            spread = ask - bid

        return Tick(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=round_price(mid),
            spread=round(spread, 3),
            high=safe_float(data.get("high")),
            low=safe_float(data.get("low")),
            day_diff_pct=safe_float(data.get("dayDiffPercent")),
            timestamp=str(data.get("timestamp", "")),
            market_state=str(data.get("marketState", "open")),
        )

    def get_ohlc(
        self, symbol: str = DEFAULT_SYMBOL, interval: str = "15m", limit: int = 1000
    ) -> List[Candle]:
        """Return closed candles oldest -> newest."""
        try:
            data = self._get(
                f"{symbol}/ohlc",
                params={"interval": interval, "limit": min(limit, 1000)},
            )
        except DataSourceError as exc:
            logger.error("OHLC fetch failed for %s %s: %s", symbol, interval, exc)
            return []

        if not data or "bars" not in data:
            logger.error("No OHLC data for %s %s", symbol, interval)
            return []

        candles: List[Candle] = []
        for bar in data["bars"]:
            if bar.get("isOpen"):
                continue
            candle = Candle(
                time=str(bar.get("openTime", "")),
                open=safe_float(bar.get("open")),
                high=safe_float(bar.get("high")),
                low=safe_float(bar.get("low")),
                close=safe_float(bar.get("close")),
                volume=safe_float(bar.get("volume")),
                tick_volume=safe_float(bar.get("tickVolume")),
                is_open=bool(bar.get("isOpen", False)),
            )
            if candle.high >= candle.low and candle.open > 0 and candle.close > 0:
                candles.append(candle)

        candles.reverse()  # API returns newest -> oldest
        return candles

    def health_check(self) -> bool:
        try:
            tick = self.get_tick()
            return tick is not None and tick.mid > 0
        except Exception:  # noqa: BLE001
            return False

    @property
    def last_success_age(self) -> float:
        if not self._last_success:
            return float("inf")
        return time.time() - self._last_success
