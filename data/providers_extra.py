"""Additional data providers — yfinance fallback, CSV, generic REST, provider router."""
from __future__ import annotations
import csv
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from config.constants import DEFAULT_SYMBOL
from core.logging_config import get_logger
from core.utils import safe_float
from .base import Candle, DataSource, Tick

logger = get_logger("data.providers")


class CSVDataSource(DataSource):
    """Load candles from a local CSV file (for backtesting)."""

    name = "csv"

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._candles: List[Candle] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.csv_path):
            logger.error("CSV file not found: %s", self.csv_path)
            return
        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                self._candles.append(Candle(
                    time=row.get("time", row.get("date", "")),
                    open=safe_float(row.get("open")),
                    high=safe_float(row.get("high")),
                    low=safe_float(row.get("low")),
                    close=safe_float(row.get("close")),
                    volume=safe_float(row.get("volume", 0)),
                ))
        logger.info("Loaded %d candles from %s", len(self._candles), self.csv_path)

    def get_tick(self, symbol: str = DEFAULT_SYMBOL) -> Optional[Tick]:
        if not self._candles:
            return None
        last = self._candles[-1]
        return Tick(symbol=symbol, bid=last.close, ask=last.close, mid=last.close,
                    spread=0.0, high=last.high, low=last.low, timestamp=last.time)

    def get_ohlc(self, symbol: str, interval: str = "", limit: int = 1000) -> List[Candle]:
        return self._candles[-limit:]

    def health_check(self) -> bool:
        return len(self._candles) > 0


class GenericRESTDataSource(DataSource):
    """Generic REST API provider — configurable via URL template."""

    name = "generic_rest"

    def __init__(self, base_url: str, ohlc_path: str = "{symbol}/ohlc",
                 tick_path: str = "{symbol}", interval_param: str = "interval",
                 limit_param: str = "limit", bars_key: str = "bars"):
        self.base_url = base_url.rstrip("/")
        self.ohlc_path = ohlc_path
        self.tick_path = tick_path
        self.interval_param = interval_param
        self.limit_param = limit_param
        self.bars_key = bars_key

    def _get_json(self, url: str) -> Optional[Dict]:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "XAUUSD-Pro-Bot/3.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.error("REST fetch failed %s: %s", url, exc)
            return None

    def get_tick(self, symbol: str = DEFAULT_SYMBOL) -> Optional[Tick]:
        data = self._get_json(f"{self.base_url}/{self.tick_path.format(symbol=symbol)}")
        if not data:
            return None
        bid = safe_float(data.get("bid", data.get("price")))
        ask = safe_float(data.get("ask", data.get("price")))
        mid = (bid + ask) / 2 if bid and ask else safe_float(data.get("mid", data.get("price")))
        return Tick(symbol=symbol, bid=bid, ask=ask, mid=mid, spread=abs(ask - bid),
                    high=safe_float(data.get("high")), low=safe_float(data.get("low")),
                    timestamp=str(data.get("timestamp", "")))

    def get_ohlc(self, symbol: str, interval: str = "15m", limit: int = 1000) -> List[Candle]:
        url = (f"{self.base_url}/{self.ohlc_path.format(symbol=symbol)}"
               f"?{self.interval_param}={interval}&{self.limit_param}={limit}")
        data = self._get_json(url)
        if not data or self.bars_key not in data:
            return []
        candles = []
        for b in data[self.bars_key]:
            if b.get("isOpen"):
                continue
            candles.append(Candle(
                time=str(b.get("openTime", b.get("time", ""))),
                open=safe_float(b.get("open")), high=safe_float(b.get("high")),
                low=safe_float(b.get("low")), close=safe_float(b.get("close")),
                volume=safe_float(b.get("volume", 0)),
            ))
        candles.reverse()
        return candles

    def health_check(self) -> bool:
        return self.get_tick() is not None


class ProviderRouter:
    """Fallback chain: try primary provider, fall back to secondary on failure."""

    def __init__(self, providers: List[DataSource]):
        self.providers = providers
        self._active_idx = 0

    @property
    def active(self) -> DataSource:
        return self.providers[self._active_idx]

    def get_tick(self, symbol: str = DEFAULT_SYMBOL) -> Optional[Tick]:
        for i, provider in enumerate(self.providers):
            try:
                tick = provider.get_tick(symbol)
                if tick:
                    if i != self._active_idx:
                        logger.info("Switched to provider %s", provider.name)
                        self._active_idx = i
                    return tick
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider %s failed: %s", provider.name, exc)
        return None

    def get_ohlc(self, symbol: str, interval: str, limit: int = 1000) -> List[Candle]:
        for provider in self.providers:
            try:
                candles = provider.get_ohlc(symbol, interval, limit)
                if candles:
                    return candles
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider %s OHLC failed: %s", provider.name, exc)
        return []

    def health(self) -> Dict[str, bool]:
        return {p.name: p.health_check() for p in self.providers}
