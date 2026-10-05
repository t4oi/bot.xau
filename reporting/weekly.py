"""Weekly report generator."""
from __future__ import annotations
from datetime import datetime, timedelta

from ..telegram_bot.formatter import SignalFormatter


class WeeklyReport:
    """Builds and sends weekly performance report."""

    def __init__(self, telegram_client, repository):
        self.tg = telegram_client
        self.repo = repository
        self.formatter = SignalFormatter()

    def generate_and_send(self, chat_id: str = "") -> bool:
        if not self.repo:
            return False
        week_ago = datetime.utcnow() - timedelta(days=7)
        # Aggregate from performance snapshots
        snapshots = self.repo.performance_history(days=7)
        total_signals = sum(s.total_signals for s in snapshots)
        total_pnl = sum(s.total_pnl_usd for s in snapshots)
        avg_wr = sum(s.win_rate_pct or 0 for s in snapshots) / max(1, len(snapshots))
        text = (
            f"📅 <b>تقرير أسبوعي</b>\n\n"
            f"📨 إشارات: <b>{total_signals}</b>\n"
            f"🎯 متوسط نسبة النجاح: <b>{avg_wr:.1f}%</b>\n"
            f"💰 صافي الربح: <b>${total_pnl:.2f}</b>\n"
        )
        return self.tg.send_message(text, chat_id)
