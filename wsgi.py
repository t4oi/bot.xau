"""WSGI entry point for Render / gunicorn.
Starts the scanner + Telegram bot + signal monitor in background threads and
exposes the Flask dashboard as the WSGI app. Bind to $PORT (Render sets it).
"""
from __future__ import annotations
import os
import sys
import threading
import time

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


def _poll_telegram(handler, client, log):
    """Long-poll Telegram for commands & button callbacks (background thread)."""
    offset = 0
    while True:
        try:
            updates = client.get_updates(offset=offset, timeout=25)
            for upd in updates:
                offset = upd["update_id"] + 1
                cb = upd.get("callback_query")
                msg = upd.get("message") or (cb.get("message") if cb else None)
                if not msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                if cb:
                    data = cb.get("data", "")
                    try:
                        handler.handle_callback(chat_id, data)
                    except Exception as exc:  # noqa: BLE001
                        log.error("Callback handling failed: %s", exc)
                else:
                    text = msg.get("text", "")
                    try:
                        handler.handle(chat_id, text)
                    except Exception as exc:  # noqa: BLE001
                        log.error("Message handling failed: %s", exc)
            if not updates:
                time.sleep(2)
        except Exception as exc:  # noqa: BLE001
            log.error("Telegram polling error: %s", exc)
            time.sleep(5)


def _start_background():
    """Start scanner + telegram + monitor + jobs in background; never crash the web worker."""
    try:
        from data.feed import FeedManager
        from risk.limits import RiskLimits
        from risk.position_sizer import PositionSizer
        from signals.tp_sl_calculator import TpSlCalculator
        from signals.filters import SignalFilter
        from signals.generator import SignalGenerator
        from strategies.multi_tf_confluence import MultiTimeframeConfluence
        from telegram_bot.client import TelegramClient
        from telegram_bot.handlers import CommandHandler
        from scheduler.loop import ScanLoop
        from scheduler.jobs import JobScheduler
        from execution.signal_monitor import SignalMonitor

        feed = FeedManager()
        risk = RiskLimits(max_daily_losses=settings.max_daily_losses,
                          account_balance=settings.account_balance_usd)
        sizer = PositionSizer(settings.account_balance_usd, settings.risk_per_trade_pct)
        calc = TpSlCalculator(atr_period=settings.atr_period,
                              sl_multiplier=settings.atr_sl_multiplier,
                              tp_multipliers=settings.tp_multipliers_list)
        filt = SignalFilter(min_confluence=settings.min_confluence_score,
                            min_rr=settings.min_risk_reward,
                            cooldown_minutes=settings.signal_cooldown_minutes)
        gen = SignalGenerator(calculator=calc, signal_filter=filt,
                              min_confluence=settings.min_confluence_score)
        mtf = MultiTimeframeConfluence(timeframes=settings.timeframe_list)
        tg = TelegramClient(token=settings.telegram_bot_token,
                            default_chat_id=settings.telegram_chat_id)

        # Signal monitor: watches price and alerts on TP1/TP2/TP3/SL hits
        monitor = SignalMonitor(telegram=tg, feed=feed, repository=repo,
                                interval_seconds=settings.monitor_interval_seconds)

        loop = ScanLoop(feed=feed, mtf=mtf, generator=gen, telegram=tg,
                        risk_limits=risk, position_sizer=sizer, repository=repo,
                        interval_seconds=settings.scan_interval_seconds,
                        monitor=monitor)

        # Re-monitor already-open signals after a restart so no TP alert is missed
        if repo:
            try:
                for rec in repo.recent_signals(limit=20):
                    if getattr(rec, "outcome", "OPEN") == "OPEN":
                        monitor.add_from_record(rec)
                log.info("Re-monitored %d open signals from DB", monitor.active_count())
            except Exception as exc:  # noqa: BLE001
                log.warning("Re-monitor on boot failed: %s", exc)

        monitor.start()
        loop.start(blocking=False)
        log.info("Background scanner started (interval=%ds)", settings.scan_interval_seconds)

        # Telegram command/button handler + polling (makes inline buttons work)
        handler = CommandHandler(tg, bot_state=loop.state, monitor=monitor,
                                 repository=repo, scan_loop=loop)
        tg_thread = threading.Thread(target=_poll_telegram, args=(handler, tg, log),
                                     daemon=True, name="telegram-poll")
        tg_thread.start()
        log.info("Telegram polling started (buttons now active)")

        # Periodic jobs: heartbeat, daily report, redelivery of failed sends
        jobs = JobScheduler(telegram=tg, repository=repo, scan_loop=loop)
        jobs.start()
        log.info("Background jobs started")
    except Exception as exc:  # noqa: BLE001
        log.error("Background scanner failed to start: %s", exc, exc_info=True)


# Start background work exactly once (gunicorn --workers 1)
threading.Thread(target=_start_background, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.web_port)
