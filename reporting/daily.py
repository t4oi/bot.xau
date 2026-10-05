"""Daily report generator."""
from __future__ import annotations
from ..telegram_bot.formatter import SignalFormatter


class DailyReport:
    """Builds and sends daily performance report."""

    def __init__(self, telegram_client, repository):
        self.tg = telegram_client
        self.repo = repository
        self.formatter = SignalFormatter()

    def generate_and_send(self, chat_id: str = "") -> bool:
        stats = self.repo.daily_stats() if self.repo else {}
        text = self.formatter.format_daily_report(stats)
        return self.tg.send_message(f"📅 <b>تقرير يومي</b>\n\n{text}", chat_id)
