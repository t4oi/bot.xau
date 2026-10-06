"""Session manager — identifies market session and applies volatility weighting."""
from __future__ import annotations
from typing import Optional

from config.constants import MarketSession, SESSION_WINDOWS
from core.utils import now_utc


class SessionManager:
    """Determines current trading session and its volatility profile."""

    @staticmethod
    def current_session(utc_hour: Optional[int] = None) -> MarketSession:
        hour = utc_hour if utc_hour is not None else now_utc().hour
        # Overlap takes precedence
        ol_start, ol_end, _ = SESSION_WINDOWS[MarketSession.OVERLAP_LN_NY]
        if ol_start <= hour < ol_end:
            return MarketSession.OVERLAP_LN_NY
        for session, (start, end, _) in SESSION_WINDOWS.items():
            if session == MarketSession.OVERLAP_LN_NY:
                continue
            if start <= hour < end:
                return session
        return MarketSession.PACIFIC

    @staticmethod
    def volatility_multiplier(session: Optional[MarketSession] = None) -> float:
        sess = session or SessionManager.current_session()
        return SESSION_WINDOWS.get(sess, (0, 0, 1.0))[2]

    @staticmethod
    def is_preferred(session: Optional[MarketSession] = None) -> bool:
        from config.constants import PREFERRED_SESSIONS
        sess = session or SessionManager.current_session()
        return sess in PREFERRED_SESSIONS

    @staticmethod
    def market_open(day_of_week: Optional[int] = None) -> bool:
        """Gold trades ~24/5. Closed weekend (Sat=5, Sun=6)."""
        dow = day_of_week if day_of_week is not None else now_utc().weekday()
        return dow < 5  # Monday=0 .. Friday=4
