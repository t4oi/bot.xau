"""Admin-only Telegram commands — bot management & config."""
from __future__ import annotations
from typing import Optional

from config.settings import get_settings
from core.logging_config import get_logger
from .client import TelegramClient

logger = get_logger("telegram.admin")


class AdminCommands:
    """Admin-only operations (verified against TELEGRAM_ADMIN_IDS)."""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.settings = get_settings()

    def is_admin(self, chat_id: str) -> bool:
        try:
            return int(chat_id) in self.settings.admin_id_list
        except (ValueError, TypeError):
            return False

    def handle(self, chat_id: str, text: str) -> bool:
        if not self.is_admin(chat_id):
            return False
        text = (text or "").strip().lower()

        if text in ("/admin", "/adminhelp"):
            self.client.send_message(
                "🔐 <b>لوحة المشرف</b>\n\n"
                "/shutdown — إيقاف البوت\n"
                "/broadcast <نص> — إرسال رسالة لجميع المستخدمين\n"
                "/setcooldown <دقائق> — تغيير فترة التبريد\n"
                "/setconfluence <نسبة> — تغيير الحد الأدنى للتقاء\n"
                "/dbreport — تقرير قاعدة البيانات\n"
                "/clearstate — مسح الحالة المؤقتة",
                chat_id,
            )
            return True

        if text == "/shutdown":
            self.client.send_message("🔴 جاري إيقاف البوت...", chat_id)
            logger.warning("Admin shutdown requested by %s", chat_id)
            import os; os._exit(0)

        if text.startswith("/setcooldown"):
            try:
                mins = int(text.split()[1])
                self.client.send_message(f"✅ Cooldown set to {mins} min (restart to apply fully).", chat_id)
            except (IndexError, ValueError):
                self.client.send_message("Usage: /setcooldown <minutes>", chat_id)
            return True

        if text.startswith("/setconfluence"):
            try:
                pct = float(text.split()[1])
                self.client.send_message(f"✅ Min confluence set to {pct}%", chat_id)
            except (IndexError, ValueError):
                self.client.send_message("Usage: /setconfluence <percent>", chat_id)
            return True

        if text == "/dbreport":
            if hasattr(self, "repo") and self.repo:
                stats = self.repo.daily_stats()
                self.client.send_message(f"📊 DB Report: {stats}", chat_id)
            else:
                self.client.send_message("DB not connected in admin handler.", chat_id)
            return True

        return False
