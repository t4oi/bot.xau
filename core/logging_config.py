"""Centralised logging configuration with rotation and colour."""
from __future__ import annotations
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

try:
    import colorlog
    _HAS_COLOR = True
except ImportError:  # pragma: no cover
    _HAS_COLOR = False

from ..config.constants import APP_NAME, DEFAULT_LOG_DIR

_LOGGER_CACHE: dict = {}


def _ensure_log_dir(log_file: str) -> None:
    directory = os.path.dirname(log_file) or DEFAULT_LOG_DIR
    os.makedirs(directory, exist_ok=True)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 7,
) -> logging.Logger:
    """Configure root logger once; return the application logger."""
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Console handler (coloured if colorlog is available)
    if _HAS_COLOR:
        console_fmt = colorlog.ColoredFormatter(
            "%(log_color)s" + fmt,
            datefmt=datefmt,
            log_colors={
                "DEBUG": "cyan", "INFO": "green", "WARNING": "yellow",
                "ERROR": "red", "CRITICAL": "bold_red",
            },
        )
    else:  # pragma: no cover
        console_fmt = logging.Formatter(fmt, datefmt=datefmt)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File handler with rotation
    if log_file:
        _ensure_log_dir(log_file)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        logger.addHandler(file_handler)

    _LOGGER_CACHE[APP_NAME] = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a child logger; ensures root is configured."""
    if APP_NAME not in _LOGGER_CACHE:
        setup_logging()
    return logging.getLogger(f"{APP_NAME}.{name}" if name else APP_NAME)


def set_log_level(level: str) -> None:
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
