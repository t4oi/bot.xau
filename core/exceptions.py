"""Custom exception hierarchy for the bot."""
from __future__ import annotations


class BotError(Exception):
    """Base exception for all bot-related errors."""

    def __init__(self, message: str = "", *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class ConfigError(BotError):
    """Raised when configuration is missing or invalid."""


class DataSourceError(BotError):
    """Raised when the market-data provider fails."""

    def __init__(self, message: str = "", *, provider: str = "", retryable: bool = True):
        super().__init__(message, retryable=retryable)
        self.provider = provider


class TelegramError(BotError):
    """Raised when Telegram API calls fail."""


class RiskLimitError(BotError):
    """Raised when a signal would breach a risk limit."""

    def __init__(self, message: str = "", *, limit_name: str = ""):
        super().__init__(message, retryable=False)
        self.limit_name = limit_name


class StrategyError(BotError):
    """Raised when a strategy encounters invalid data."""


class DatabaseError(BotError):
    """Raised on persistence failures."""


class BacktestError(BotError):
    """Raised during backtesting engine failures."""


class WebDashboardError(BotError):
    """Raised by the web dashboard layer."""
