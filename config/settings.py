"""
Settings loader — reads environment variables with sane defaults.
Uses pydantic v2 for validation. All sensitive values live here.
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import (
    DEFAULT_SYMBOL, SCAN_TIMEFRAMES, DEFAULT_DB_PATH,
    DEFAULT_LOG_DIR, HTTP_TIMEOUT_SECONDS,
)


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(default="8503353625:AAG9mQcYrYzbeZGfE6vVBcPeQsFBCsbyfHw", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="8952278702", alias="TELEGRAM_CHAT_ID")
    telegram_admin_ids: str = Field(default="8952278702", alias="TELEGRAM_ADMIN_IDS")

    # --- Data source ---
    data_source: str = Field(default="biquote", alias="DATA_SOURCE")
    biquote_base_url: str = Field(
        default="https://biquote.io/api", alias="BIQUOTE_BASE_URL"
    )
    trading_symbol: str = Field(default=DEFAULT_SYMBOL, alias="TRADING_SYMBOL")

    # --- Trading / risk ---
    account_balance_usd: float = Field(default=1000.0, alias="ACCOUNT_BALANCE_USD")
    risk_per_trade_pct: float = Field(default=1.0, alias="RISK_PER_TRADE_PCT")
    max_daily_losses: int = Field(default=3, alias="MAX_DAILY_LOSSES")
    max_daily_loss_pct: float = Field(default=5.0, alias="MAX_DAILY_LOSS_PCT")
    max_drawdown_pct: float = Field(default=15.0, alias="MAX_DRAWDOWN_PCT")
    min_risk_reward: float = Field(default=1.5, alias="MIN_RISK_REWARD")
    default_take_profits: int = Field(default=3, alias="DEFAULT_TAKE_PROFITS")
    atr_period: int = Field(default=14, alias="ATR_PERIOD")
    atr_sl_multiplier: float = Field(default=1.5, alias="ATR_SL_MULTIPLIER")
    atr_tp_multiplier: float = Field(default=3.0, alias="ATR_TP_MULTIPLIER")

    # --- Analysis ---
    active_timeframes: str = Field(
        default=",".join(SCAN_TIMEFRAMES), alias="ACTIVE_TIMEFRAMES"
    )
    primary_timeframe: str = Field(default="15m", alias="PRIMARY_TIMEFRAME")
    higher_timeframe: str = Field(default="4h", alias="HIGHER_TIMEFRAME")
    min_confluence_score: int = Field(default=65, alias="MIN_CONFLUENCE_SCORE")
    signal_cooldown_minutes: int = Field(default=30, alias="SIGNAL_COOLDOWN_MINUTES")

    # --- Database ---
    database_url: str = Field(default=f"sqlite:///{DEFAULT_DB_PATH}", alias="DATABASE_URL")

    # --- Logging ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default=f"{DEFAULT_LOG_DIR}/bot.log", alias="LOG_FILE")

    # --- Web dashboard ---
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=int(os.environ.get("PORT", os.environ.get("WEB_PORT", "8080"))), alias="WEB_PORT")
    web_username: str = Field(default="admin", alias="WEB_USERNAME")
    web_password: str = Field(default="changeme123", alias="WEB_PASSWORD")

    # --- Scheduler ---
    scan_interval_seconds: int = Field(default=60, alias="SCAN_INTERVAL_SECONDS")
    heartbeat_interval_seconds: int = Field(default=300, alias="HEARTBEAT_INTERVAL_SECONDS")
    http_timeout_seconds: int = Field(default=HTTP_TIMEOUT_SECONDS, alias="HTTP_TIMEOUT_SECONDS")

    # ------------------------------------------------------------------
    @field_validator("telegram_admin_ids")
    @classmethod
    def _split_admin_ids(cls, v: str) -> str:
        return v  # kept as string; parsed via property below

    @property
    def admin_id_list(self) -> List[int]:
        if not self.telegram_admin_ids:
            return []
        return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip().isdigit()]

    @property
    def timeframe_list(self) -> List[str]:
        return [t.strip() for t in self.active_timeframes.split(",") if t.strip()]

    def is_admin(self, chat_id: int) -> bool:
        return chat_id in self.admin_id_list

    def validate_credentials(self) -> List[str]:
        """Return list of missing/empty critical config items."""
        missing: List[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if not self.biquote_base_url:
            missing.append("BIQUOTE_BASE_URL")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor."""
    return Settings()


def reload_settings() -> Settings:
    """Force re-read from environment (useful in tests)."""
    get_settings.cache_clear()
    return get_settings()
