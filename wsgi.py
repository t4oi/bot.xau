"""WSGI entry point for Render / gunicorn.
Starts the scanner + Telegram bot in background threads and exposes
the Flask dashboard as the WSGI app. Bind to $PORT (Render sets it).
"""
from __future__ import annotations
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logging_config import setup_logging, get_logger
from config.settings import get_settings

logger = setup_logging()
log = get_logger("wsgi")

# Build the Flask app (imports must succeed for web to serve)
from web.app import create_app
from database.repository import Repository

settings = get_settings()
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

try:
    repo = Repository(settings.database_url)
except Exception as exc:  # noqa: BLE001
    log.warning("DB init failed (continuing without persistence): %s", exc)
    repo = None

app = create_app(repository=repo)


def _start_background():
    """Start scanner + telegram in background; never crash the web worker."""
    try:
        from data.feed import FeedManager
        from risk.limits import RiskLimits
        from risk.position_sizer import PositionSizer
        from signals.tp_sl_calculator import TpSlCalculator
        from signals.filters import SignalFilter
        from signals.generator import SignalGenerator
        from strategies.multi_tf_confluence import MultiTimeframeConfluence
        from telegram_bot.client import TelegramClient
        from scheduler.loop import ScanLoop

        feed = FeedManager()
        risk = RiskLimits(max_daily_losses=settings.max_daily_losses,
                          account_balance=settings.account_balance_usd)
        sizer = PositionSizer(settings.account_balance_usd, settings.risk_per_trade_pct)
        calc = TpSlCalculator(atr_period=settings.atr_period,
                              sl_multiplier=settings.atr_sl_multiplier)
        filt = SignalFilter(min_confluence=settings.min_confluence_score,
                            min_rr=settings.min_risk_reward,
                            cooldown_minutes=settings.signal_cooldown_minutes)
        gen = SignalGenerator(calculator=calc, signal_filter=filt,
                              min_confluence=settings.min_confluence_score)
        mtf = MultiTimeframeConfluence(timeframes=settings.timeframe_list)
        tg = TelegramClient(token=settings.telegram_bot_token,
                            default_chat_id=settings.telegram_chat_id)
        loop = ScanLoop(feed=feed, mtf=mtf, generator=gen, telegram=tg,
                        risk_limits=risk, position_sizer=sizer, repository=repo,
                        interval_seconds=settings.scan_interval_seconds)
        loop.start(blocking=False)
        log.info("Background scanner started (interval=%ds)", settings.scan_interval_seconds)
    except Exception as exc:  # noqa: BLE001
        log.error("Background scanner failed to start: %s", exc, exc_info=True)


# Start background work exactly once (gunicorn --workers 1)
threading.Thread(target=_start_background, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.web_port)
