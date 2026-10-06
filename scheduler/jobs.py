"""Periodic jobs: heartbeat, daily report, performance snapshot, cleanup."""
from __future__ import annotations
import threading
import time
from typing import Optional

from core.logging_config import get_logger
from telegram_bot.client import TelegramClient
from telegram_bot.formatter import SignalFormatter

logger = get_logger("scheduler.jobs")


class JobScheduler:
    """Runs periodic background jobs."""

    def __init__(self, telegram: TelegramClient, repository=None, scan_loop=None):
        self.telegram = telegram
        self.repo = repository
        self.scan_loop = scan_loop
        self.formatter = SignalFormatter()
        self._stop = threading.Event()
        self._threads = []
        self._last_heartbeat_alert = 0.0  # alert cooldown

    def _heartbeat(self, interval: int = 300) -> None:
        while not self._stop.is_set():
            try:
                if self.scan_loop:
                    last = self.scan_loop.state.last_scan
                    if last > 0:  # only alert if at least one scan has run
                        age = time.time() - last
                        if age > interval * 3 and time.time() - self._last_heartbeat_alert > 3600:
                            self.telegram.send_message(
                                f"⚠️ <b>تنبيه:</b> آخر فحص كان منذ {age/60:.0f} دقيقة — قد يكون هناك عطل."
                            )
                            self._last_heartbeat_alert = time.time()
                logger.info("Heartbeat OK")
            except Exception as exc:  # noqa: BLE001
                logger.error("Heartbeat failed: %s", exc)
            self._stop.wait(interval)

    def _daily_report(self, hour_utc: int = 21) -> None:
        while not self._stop.is_set():
            try:
                from core.utils import now_utc
                if now_utc().hour == hour_utc and self.repo:
                    stats = self.repo.daily_stats()
                    self.telegram.send_message(self.formatter.format_daily_report(stats))
                    self.repo.save_snapshot({
                        "total_signals": stats["signals_sent"],
                        "win_rate_pct": stats["win_rate"],
                        "total_pnl_usd": stats["pnl"],
                    })
            except Exception as exc:  # noqa: BLE001
                logger.error("Daily report failed: %s", exc)
            self._stop.wait(3600)  # check hourly

    def _performance_snapshot(self, interval: int = 3600) -> None:
        while not self._stop.is_set():
            if self.repo:
                try:
                    stats = self.repo.daily_stats()
                    self.repo.save_snapshot({
                        "total_signals": stats["signals_sent"],
                        "total_trades": stats["wins"] + stats["losses"],
                        "win_rate_pct": stats["win_rate"],
                        "total_pnl_usd": stats["pnl"],
                    })
                except Exception as exc:  # noqa: BLE001
                    logger.error("Snapshot failed: %s", exc)
            self._stop.wait(interval)

    def start(self) -> None:
        jobs = [
            ("heartbeat", self._heartbeat, (300,)),
            ("daily_report", self._daily_report, (21,)),
            ("snapshot", self._performance_snapshot, (3600,)),
        ]
        for name, fn, args in jobs:
            t = threading.Thread(target=fn, args=args, daemon=True, name=name)
            t.start()
            self._threads.append(t)
        logger.info("Started %d background jobs", len(self._threads))

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)
