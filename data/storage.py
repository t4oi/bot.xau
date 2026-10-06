"""Persistent candle storage (CSV + parquet optional) for historical data."""
from __future__ import annotations
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

from config.constants import DEFAULT_DATA_DIR
from core.logging_config import get_logger
from .base import Candle

logger = get_logger("data.storage")


class CandleStore:
    """Append-only CSV store keyed by (symbol, interval)."""

    def __init__(self, base_dir: str = DEFAULT_DATA_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _path(self, symbol: str, interval: str) -> str:
        safe = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(self.base_dir, f"{safe}_{interval}.csv")

    def append(self, symbol: str, interval: str, candles: List[Candle]) -> int:
        """Append new candles; dedupe by open time. Returns count added."""
        path = self._path(symbol, interval)
        existing_times = set()
        if os.path.exists(path):
            with open(path, "r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                existing_times = {row["time"] for row in reader}

        new_rows = [c for c in candles if c.time not in existing_times]
        if not new_rows:
            return 0

        write_header = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow(["time", "open", "high", "low", "close",
                                 "volume", "tick_volume", "is_open"])
            for c in new_rows:
                writer.writerow([c.time, c.open, c.high, c.low, c.close,
                                 c.volume, c.tick_volume, int(c.is_open)])
        logger.info("Stored %d new candles for %s %s", len(new_rows), symbol, interval)
        return len(new_rows)

    def load(self, symbol: str, interval: str, limit: Optional[int] = None) -> List[Candle]:
        path = self._path(symbol, interval)
        if not os.path.exists(path):
            return []
        rows: List[Candle] = []
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(Candle(
                    time=row["time"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                    tick_volume=float(row.get("tick_volume", 0)),
                    is_open=bool(int(row.get("is_open", 0))),
                ))
        if limit:
            rows = rows[-limit:]
        return rows

    def stats(self) -> Dict[str, int]:
        result = {}
        for fname in os.listdir(self.base_dir):
            if fname.endswith(".csv"):
                key = fname[:-4]
                with open(os.path.join(self.base_dir, fname), "r", encoding="utf-8") as fh:
                    result[key] = sum(1 for _ in fh) - 1
        return result
