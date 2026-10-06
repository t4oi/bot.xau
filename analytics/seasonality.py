"""Seasonality analyzer — hourly/daily patterns in XAUUSD."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple

from data.base import Candle
from core.utils import to_utc


class SeasonalityAnalyzer:
    """Detects seasonal patterns by hour-of-day and day-of-week."""

    def __init__(self):
        self.hourly_returns: Dict[int, List[float]] = defaultdict(list)
        self.daily_returns: Dict[int, List[float]] = defaultdict(list)
        self.session_returns: Dict[str, List[float]] = defaultdict(list)

    def add_candles(self, candles: List[Candle]) -> None:
        for i in range(1, len(candles)):
            ret = (candles[i].close - candles[i - 1].close) / candles[i - 1].close * 100
            ts = to_utc(candles[i].time)
            if ts is None:
                continue
            self.hourly_returns[ts.hour].append(ret)
            self.daily_returns[ts.weekday()].append(ret)
            hour = ts.hour
            if 7 <= hour < 12:
                sess = "LONDON"
            elif 12 <= hour < 17:
                sess = "NEW_YORK"
            elif 12 <= hour < 16:
                sess = "OVERLAP"
            elif 0 <= hour < 7:
                sess = "ASIA"
            else:
                sess = "PACIFIC"
            self.session_returns[sess].append(ret)

    def hourly_profile(self) -> Dict[int, Dict[str, float]]:
        result = {}
        for hour, rets in self.hourly_returns.items():
            if rets:
                result[hour] = {
                    "avg_return": round(sum(rets) / len(rets), 4),
                    "volatility": round((sum(r ** 2 for r in rets) / len(rets)) ** 0.5, 4),
                    "samples": len(rets),
                    "win_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                }
        return result

    def daily_profile(self) -> Dict[str, Dict[str, float]]:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        result = {}
        for dow, rets in self.daily_returns.items():
            if rets:
                result[day_names[dow]] = {
                    "avg_return": round(sum(rets) / len(rets), 4),
                    "volatility": round((sum(r ** 2 for r in rets) / len(rets)) ** 0.5, 4),
                    "samples": len(rets),
                }
        return result

    def session_profile(self) -> Dict[str, Dict[str, float]]:
        result = {}
        for sess, rets in self.session_returns.items():
            if rets:
                result[sess] = {
                    "avg_return": round(sum(rets) / len(rets), 4),
                    "volatility": round((sum(r ** 2 for r in rets) / len(rets)) ** 0.5, 4),
                    "win_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                    "samples": len(rets),
                }
        return result

    def best_session(self) -> Tuple[str, float]:
        profile = self.session_profile()
        if not profile:
            return ("UNKNOWN", 0.0)
        best = max(profile.items(), key=lambda kv: kv[1]["avg_return"])
        return best[0], best[1]["avg_return"]
