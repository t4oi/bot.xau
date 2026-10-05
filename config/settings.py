"""
Settings and configuration loader using Pydantic.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str = ""
    telegram_chat_id: str = ""
    biquote_base_url: str = "https://biquote.com/api"
    trading_symbol: str = "XAUUSD"
    http_timeout_seconds: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance
