#!/usr/bin/env python3
"""
XAUUSD Pro Signal Bot — main entry point.
Usage:
    python run.py              # start full bot (scanner + telegram + web dashboard)
    python run.py --no-web     # scanner + telegram only
    python run.py --web-only   # web dashboard only
    python run.py --backtest   # run backtest on stored data
    python run.py --health     # health check only
"""
from __future__ import annotations
import argparse
import os
import sys
import threading

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings, reload_settings
from core.logging_config import setup_logging, get_logger
from core.exceptions import ConfigError
from data.feed import FeedManager
from database.repository import Repository
from risk.limits import RiskLimits
from risk.position_sizer import PositionSizer
from signals.generator import SignalGenerator
from signals.filters import SignalFilter
from signals.tp_sl_calculator import TpSlCalculator
from strategies.multi_tf_confluence import MultiTimeframeConfluence
from telegram_bot.client import TelegramClient
from telegram_bot.handlers import CommandHandler
from scheduler.loop import ScanLoop
from scheduler.jobs import JobScheduler
from execution.signal_monitor import SignalMonitor


def bootstrap():
    """Initialise all components and validate config."""
    settings = get_settings()
    missing = settings.validate_credentials()
    if missing:
        raise ConfigError(f"Missing required config: {', '.join(missing)}")

    logger = setup_logging(level=settings.log_level, log_file=settings.log_file)
    logger.info("=" * 60)
    logger.info("XAUUSD Pro Signal Bot v3.0.0 starting...")
    logger.info("=" * 60)

    # Data layer
    feed = FeedManager()
    logger.info("Data source: %s (symbol=%s)", feed.source.name, feed.symbol)

    # Database
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    repo = Repository(settings.database_url)

    # Risk
    risk_limits = RiskLimits(
        max_daily_losses=settings.max_daily_losses,
        max_daily_loss_pct=settings.max_daily_loss_pct,
        max_drawdown_pct=settings.max_drawdown_pct,
        account_balance=settings.account_balance_usd,
    )
    position_sizer = PositionSizer(
        account_balance_usd=settings.account_balance_usd,
        risk_per_trade_pct=settings.risk_per_trade_pct,
    )

    # Signal pipeline
    calculator = TpSlCalculator(
        atr_period=settings.atr_period,
        sl_multiplier=settings.atr_sl_multiplier,
        tp_multipliers=settings.tp_multipliers_list,
    )
    sig_filter = SignalFilter(
        min_confluence=settings.min_confluence_score,
        min_rr=settings.min_risk_reward,
        cooldown_minutes=settings.signal_cooldown_minutes,
    )
    generator = SignalGenerator(calculator=calculator, signal_filter=sig_filter,
                                min_confluence=settings.min_confluence_score)

    # Strategies
    mtf = MultiTimeframeConfluence(timeframes=settings.timeframe_list)

    # Telegram
    telegram = TelegramClient(
        token=settings.telegram_bot_token,
        default_chat_id=settings.telegram_chat_id,
    )
    me = telegram.get_me()
    if me:
        logger.info("Telegram bot connected: @%s", me.get("username"))
    else:
        logger.warning("Could not verify Telegram bot token — check connectivity")

    # Signal monitor: watches price and alerts on TP1/TP2/TP3/SL hits
    monitor = SignalMonitor(telegram=telegram, feed=feed, repository=repo,
                            interval_seconds=settings.monitor_interval_seconds)

    # Scan loop
    scan_loop = ScanLoop(
        feed=feed, mtf=mtf, generator=generator, telegram=telegram,
        risk_limits=risk_limits, position_sizer=position_sizer,
        repository=repo, interval_seconds=settings.scan_interval_seconds,
        monitor=monitor,
    )

    # Command handler (for incoming Telegram messages)
    handler = CommandHandler(telegram, bot_state=scan_loop.state, monitor=monitor,
                             repository=repo, scan_loop=scan_loop)

    # Background jobs
    jobs = JobScheduler(telegram=telegram, repository=repo, scan_loop=scan_loop)

    return {
        "settings": settings, "feed": feed, "repo": repo,
        "risk_limits": risk_limits, "position_sizer": position_sizer,
        "generator": generator, "mtf": mtf, "telegram": telegram,
        "scan_loop": scan_loop, "handler": handler, "jobs": jobs, "monitor": monitor,
    }


def run_telegram_polling(handler, client, logger):
    """Long-poll Telegram for commands (background thread)."""
    offset = 0
    while True:
        try:
            updates = client.get_updates(offset=offset, timeout=25)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("callback_query", {}).get("message")
                if not msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                if "callback_query" in upd:
                    data = upd["callback_query"].get("data", "")
                    handler.handle_callback(chat_id, data)
                else:
                    text = msg.get("text", "")
                    handler.handle(chat_id, text)
            if not updates:
                import time as _t; _t.sleep(2)
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram polling error: %s", exc)
            import time; time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="XAUUSD Pro Signal Bot")
    parser.add_argument("--no-web", action="store_true", help="Disable web dashboard")
    parser.add_argument("--web-only", action="store_true", help="Run web dashboard only")
    parser.add_argument("--backtest", action="store_true", help="Run backtest")
    parser.add_argument("--health", action="store_true", help="Health check only")
    args = parser.parse_args()

    components = bootstrap()
    logger = get_logger("main")
    settings = components["settings"]

    if args.health:
        health = components["feed"].health()
        print(f"Data source healthy: {health['healthy']}")
        me = components["telegram"].get_me()
        print(f"Telegram bot: {'OK' if me else 'FAIL'}")
        sys.exit(0 if health["healthy"] and me else 1)

    if args.backtest:
        from backtest.engine import BacktestEngine
        from backtest.report import BacktestReport
        candles = components["feed"].candles(settings.primary_timeframe, limit=1000)
        if not candles:
            logger.error("No candles for backtest")
            sys.exit(1)

        def signal_fn(cs):
            from strategies.trend_following import TrendFollowingStrategy
            from config.constants import SignalDirection
            strat = TrendFollowingStrategy()
            res = strat.analyze(cs, settings.primary_timeframe)
            if res.net_direction == SignalDirection.NEUTRAL:
                return None
            entry = cs[-1].close
            risk = entry * 0.005
            sl = entry - risk if res.net_direction == SignalDirection.BUY else entry + risk
            tp = entry + 2 * risk if res.net_direction == SignalDirection.BUY else entry - 2 * risk
            return (res.net_direction, entry, sl, tp)

        engine = BacktestEngine(initial_balance=settings.account_balance_usd)
        result = engine.run(candles, signal_fn)
        print(BacktestReport.text_report(result))
        sys.exit(0)

    if args.web_only:
        from web.app import run_dashboard
        run_dashboard(components["repo"], components["scan_loop"],
                      host=settings.web_host, port=settings.web_port)
        return

    # Start scanner
    components["scan_loop"].start(blocking=False)
    components["jobs"].start()
    components["monitor"].start()

    # Telegram polling in background
    tg_thread = threading.Thread(
        target=run_telegram_polling,
        args=(components["handler"], components["telegram"], logger),
        daemon=True,
    )
    tg_thread.start()

    # Web dashboard
    if not args.no_web:
        from web.app import run_dashboard
        try:
            run_dashboard(components["repo"], components["scan_loop"],
                          host=settings.web_host, port=settings.web_port)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            components["scan_loop"].stop()
            components["jobs"].stop()
    else:
        try:
            while True:
                import time; time.sleep(60)
        except KeyboardInterrupt:
            components["scan_loop"].stop()
            components["jobs"].stop()


if __name__ == "__main__":
    main()
