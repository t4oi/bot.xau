"""Core package: shared utilities, exceptions, logging."""
from .exceptions import (
    BotError, DataSourceError, TelegramError, RiskLimitError,
    StrategyError, ConfigError, DatabaseError,
)
from .logging_config import setup_logging, get_logger
from .utils import (
    safe_float, safe_int, midpoint, round_to_digits, now_utc,
    format_price, format_pct, clamp, retry_call, chunks,
)

__all__ = [
    "BotError", "DataSourceError", "TelegramError", "RiskLimitError",
    "StrategyError", "ConfigError", "DatabaseError",
    "setup_logging", "get_logger",
    "safe_float", "safe_int", "midpoint", "round_to_digits", "now_utc",
    "format_price", "format_pct", "clamp", "retry_call", "chunks",
]
