"""In-memory TTL cache for market data to reduce API pressure."""
from __future__ import annotations
import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class DataCache:
    """Thread-safe TTL cache with max-size eviction (LRU-ish)."""

    def __init__(self, default_ttl: float = 8.0, max_entries: int = 1024):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = Lock()

    def _evict_if_needed(self) -> None:
        if len(self._store) <= self.max_entries:
            return
        # Evict oldest by insertion time
        sorted_keys = sorted(self._store, key=lambda k: self._store[k][0])
        for key in sorted_keys[: len(self._store) - self.max_entries]:
            self._store.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > self.default_ttl:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)
            self._evict_if_needed()

    def get_or_compute(self, key: str, compute_fn, ttl: Optional[float] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute_fn()
        if value is not None:
            self.set(key, value, ttl)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
