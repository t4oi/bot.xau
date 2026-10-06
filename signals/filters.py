"""Signal filters — quality gates before a signal is sent."""
from __future__ import annotations
import datetime as dt
from typing import Dict, List, Optional

from config.constants import (
    GOLD_MAX_SPREAD, MIN_RISK_REWARD_RATIO, MIN_CONFLUENCE_PCT,
    MarketSession, SESSION_WINDOWS, PREFERRED_SESSIONS,
)
from core.logging_config import get_logger
from core.utils import now_utc

logger = get_logger("signal.filters")


class SignalFilter:
    """Applies a chain of quality filters. Returns (passed, reasons)."""

    def __init__(self,
                 min_confluence: float = MIN_CONFLUENCE_PCT,
                 min_rr: float = MIN_RISK_REWARD_RATIO,
                 max_spread: float = GOLD_MAX_SPREAD,
                 cooldown_minutes: int = 30):
        self.min_confluence = min_confluence
        self.min_rr = min_rr
        self.max_spread = max_spread
        self.cooldown_minutes = cooldown_minutes
        self._last_signal_time: Dict[str, dt.datetime] = {}

    def check_spread(self, spread: float) -> tuple:
        if spread > self.max_spread:
            return False, f"Spread {spread:.2f} > max {self.max_spread}"
        return True, ""

    def check_risk_reward(self, rr: float) -> tuple:
        if rr < self.min_rr:
            return False, f"R:R {rr:.2f} < min {self.min_rr}"
        return True, ""

    def check_confluence(self, score_pct: float) -> tuple:
        if score_pct < self.min_confluence:
            return False, f"Confluence {score_pct:.1f}% < min {self.min_confluence}%"
        return True, ""

    def check_cooldown(self, symbol: str = "XAUUSD") -> tuple:
        last = self._last_signal_time.get(symbol)
        if last:
            elapsed = (now_utc() - last).total_seconds() / 60.0
            if elapsed < self.cooldown_minutes:
                return False, f"Cooldown active ({elapsed:.0f}min < {self.cooldown_minutes}min)"
        return True, ""

    def check_session(self) -> tuple:
        """Prefer London/NY/Overlap; soft filter (warns, doesn't block)."""
        hour = now_utc().hour
        for session, (start, end, _) in SESSION_WINDOWS.items():
            if start <= hour < end:
                if session in PREFERRED_SESSIONS:
                    return True, f"Session {session.value} (preferred)"
                return True, f"Session {session.value} (lower volatility)"
        return True, "Outside major sessions"

    def mark_sent(self, symbol: str = "XAUUSD") -> None:
        self._last_signal_time[symbol] = now_utc()

    def apply_all(self, *, spread: float, rr: float, confluence: float,
                  symbol: str = "XAUUSD") -> Dict:
        """Run all filters. Returns {passed, reasons: [...], session}."""
        reasons: List[str] = []
        passed = True

        for ok, reason in (
            self.check_spread(spread),
            self.check_risk_reward(rr),
            self.check_confluence(confluence),
            self.check_cooldown(symbol),
        ):
            if not ok:
                passed = False
                reasons.append(reason)

        session_ok, session_reason = self.check_session()
        reasons.append(session_reason)

        if not passed:
            logger.info("Signal filtered: %s", "; ".join(reasons))
        return {"passed": passed, "reasons": reasons, "session": session_reason}
