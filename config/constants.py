"""
Global constants & enums for the XAUUSD Pro Signal Bot.
Centralised here so every module references one source of truth.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME: str = "XAUUSD_Pro_Signal_Bot"
APP_VERSION: str = "3.0.0"
APP_AUTHOR: str = "Pro Trading Engineering"
APP_DESCRIPTION: str = (
    "Professional multi-timeframe signal engine for XAUUSD (Gold) "
    "with Telegram delivery, risk management and backtesting."
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

    @property
    def is_long(self) -> bool:
        return self == SignalDirection.BUY

    @property
    def is_short(self) -> bool:
        return self == SignalDirection.SELL


class SignalStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def minutes(self) -> int:
        mapping = {"1m": 1, "5m": 5, "15m": 15, "30m": 30,
                   "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
        return mapping[self.value]

    @property
    def weight(self) -> float:
        """Higher timeframes carry more weight in confluence scoring."""
        mapping = {"1m": 0.5, "5m": 0.7, "15m": 1.0, "30m": 1.2,
                   "1h": 1.5, "4h": 2.0, "1d": 2.5, "1w": 3.0}
        return mapping[self.value]


class MarketSession(str, Enum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP_LN_NY = "OVERLAP_LN_NY"
    PACIFIC = "PACIFIC"
    CLOSED = "CLOSED"


class TradeOutcome(str, Enum):
    OPEN = "OPEN"
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    CANCELLED = "CANCELLED"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


# ---------------------------------------------------------------------------
# Trading symbol defaults
# ---------------------------------------------------------------------------
DEFAULT_SYMBOL: str = "XAUUSD"
SYMBOL_DIGITS: int = 2
SYMBOL_POINT: float = 0.01
SYMBOL_CONTRACT_SIZE: float = 100.0          # 1 lot = 100 oz
SYMBOL_PIP_VALUE_PER_LOT_USD: float = 1.0    # $1 per 0.01 move per 1 lot (approx)
GOLD_MAX_SPREAD: float = 0.50                # reject signals if spread > 50 cents


# ---------------------------------------------------------------------------
# Timeframes used by the scanner
# ---------------------------------------------------------------------------
SCAN_TIMEFRAMES: List[str] = ["1m", "5m", "15m", "30m", "1h", "4h"]
TREND_TIMEFRAMES: List[str] = ["1h", "4h", "1d"]
ENTRY_TIMEFRAMES: List[str] = ["1m", "5m", "15m", "30m"]


# ---------------------------------------------------------------------------
# Session windows (UTC) — Gold trades nearly 24/5
# (start_hour, end_hour, volatility_multiplier)
# ---------------------------------------------------------------------------
SESSION_WINDOWS: Dict[MarketSession, Tuple[int, int, float]] = {
    MarketSession.ASIA: (0, 7, 0.7),
    MarketSession.LONDON: (7, 12, 1.2),
    MarketSession.NEW_YORK: (12, 17, 1.4),
    MarketSession.OVERLAP_LN_NY: (12, 16, 1.8),
    MarketSession.PACIFIC: (17, 24, 0.8),
}

# Best gold-trading sessions (higher signal weight)
PREFERRED_SESSIONS: List[MarketSession] = [
    MarketSession.LONDON, MarketSession.NEW_YORK, MarketSession.OVERLAP_LN_NY
]


# ---------------------------------------------------------------------------
# Indicator default periods
# ---------------------------------------------------------------------------
INDICATOR_DEFAULTS: Dict[str, Dict] = {
    "sma_fast": {"period": 20},
    "sma_slow": {"period": 50},
    "sma_trend": {"period": 200},
    "ema_fast": {"period": 12},
    "ema_slow": {"period": 26},
    "ema_signal": {"period": 9},
    "rsi": {"period": 14},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "stochastic": {"k": 14, "d": 3, "smooth": 3},
    "atr": {"period": 14},
    "bollinger": {"period": 20, "std": 2.0},
    "adx": {"period": 14},
    "ichimoku": {"tenkan": 9, "kijun": 26, "senkou": 52, "chikou": 26},
    "williams_r": {"period": 14},
    "cci": {"period": 20},
    "mfi": {"period": 14},
    "roc": {"period": 12},
    "obv": {},
    "vwap": {},
    "pivot": {"type": "classic"},
}


# ---------------------------------------------------------------------------
# Signal quality thresholds
# ---------------------------------------------------------------------------
MIN_CONFLUENCE_PCT: int = 60
STRONG_CONFLUENCE_PCT: int = 80
MIN_RISK_REWARD_RATIO: float = 1.5
MAX_SPREAD_ALLOWED: float = 0.50
MIN_CANDLES_REQUIRED: int = 200


# ---------------------------------------------------------------------------
# Telegram message limits
# ---------------------------------------------------------------------------
TG_MAX_MESSAGE_LEN: int = 4096
TG_MAX_CAPTION_LEN: int = 1024
TG_PARSE_MODE: str = "HTML"


# ---------------------------------------------------------------------------
# Retry policy for external APIs
# ---------------------------------------------------------------------------
HTTP_MAX_RETRIES: int = 3
HTTP_BACKOFF_FACTOR: float = 1.5
HTTP_TIMEOUT_SECONDS: int = 25
RATE_LIMIT_SLEEP_SECONDS: int = 5


# ---------------------------------------------------------------------------
# Database / storage
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH: str = "./data/xauusd_bot.db"
DEFAULT_LOG_DIR: str = "./logs"
DEFAULT_DATA_DIR: str = "./data"
MAX_SIGNALS_PER_DAY: int = 20


# ---------------------------------------------------------------------------
# Colour palette for terminal / web output
# ---------------------------------------------------------------------------
COLORS: Dict[str, str] = {
    "buy": "#22c55e",
    "sell": "#ef4444",
    "neutral": "#f59e0b",
    "tp": "#3b82f6",
    "sl": "#a855f7",
    "info": "#06b6d4",
}
