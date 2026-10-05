"""Extended Telegram command handlers — admin controls & advanced queries."""
from __future__ import annotations
from typing import Optional

from ..core.logging_config import get_logger
from .client import TelegramClient
from .formatter import SignalFormatter
from .keyboards import KeyboardFactory

logger = get_logger("telegram.commands")


class ExtendedCommands:
    """Additional admin & user commands beyond the basic set."""

    def __init__(self, client: TelegramClient, bot_state=None, repository=None,
                 risk_limits=None, position_sizer=None):
        self.client = client
        self.state = bot_state
        self.repo = repository
        self.risk = risk_limits
        self.sizer = position_sizer
        self.formatter = SignalFormatter()
        self.kb = KeyboardFactory()

    def handle(self, chat_id: str, text: str) -> bool:
        """Return True if command was handled here."""
        text = (text or "").strip().lower()

        if text in ("/pause", "إيقاف مؤقت"):
            if self.state:
                self.state.running = False
            self.client.send_message("⏸ تم إيقاف الفحص المؤقت. استخدم /resume للاستئناف.", chat_id)
            return True

        if text in ("/resume", "استئناف"):
            if self.state:
                self.state.running = True
            self.client.send_message("▶️ تم استئناف الفحص.", chat_id)
            return True

        if text in ("/risk", "المخاطر"):
            if self.risk:
                allowed, reason = self.risk.can_trade()
                stats = self.risk.daily_stats
                self.client.send_message(
                    f"🛡 <b>إدارة المخاطر</b>\n\n"
                    f"الحالة: {'✅ مسموح' if allowed else '⛔ محظور — ' + reason}\n"
                    f"خسائر اليوم: {stats.losses}/{self.risk.max_daily_losses}\n"
                    f"إشارات اليوم: {stats.signals_sent}\n"
                    f"صافي اليوم: ${stats.pnl_usd:.2f}\n"
                    f"الرصيد الحالي: ${self.risk.current_balance:.2f}\n"
                    f"أعلى رصيد: ${self.risk.peak_balance:.2f}",
                    chat_id,
                )
            return True

        if text in ("/open", "الصفقات المفتوحة"):
            if self.repo:
                trades = self.repo.open_trades()
                if not trades:
                    self.client.send_message("لا توجد صفقات مفتوحة حالياً.", chat_id)
                else:
                    lines = [f"• {t.direction} {t.symbol} @ {t.entry_price:.2f} "
                             f"(SL={t.stop_loss:.2f}, TP={t.take_profit:.2f})" for t in trades]
                    self.client.send_message("📂 <b>الصفقات المفتوحة:</b>\n" + "\n".join(lines), chat_id)
            return True

        if text in ("/export", "تصدير"):
            if self.repo:
                signals = self.repo.recent_signals(50)
                lines = [f"{s.created_at} | {s.direction} | {s.entry:.2f} | "
                         f"conf={s.confluence_pct:.0f}% | {s.outcome}" for s in signals]
                self.client.send_message("<pre>" + "\n".join(lines[:30]) + "</pre>", chat_id)
            return True

        if text.startswith("/setrisk"):
            try:
                pct = float(text.split()[1])
                if self.sizer:
                    self.sizer.risk_per_trade_pct = pct
                self.client.send_message(f"✅ تم تحديث نسبة المخاطرة إلى {pct}%", chat_id)
            except (IndexError, ValueError):
                self.client.send_message("استخدام: /setrisk <نسبة مئوية> مثال: /setrisk 1.5", chat_id)
            return True

        if text in ("/strategies", "الاستراتيجيات"):
            from ..strategies.registry import get_registry
            reg = get_registry()
            names = "\n".join(f"• {n}" for n in reg.all_names())
            self.client.send_message(f"🧠 <b>الاستراتيجيات النشطة ({len(reg)}):</b>\n{names}", chat_id)
            return True

        if text in ("/profile", "الملف"):
            from ..config.profiles import list_profiles
            self.client.send_message(f"⚙️ الملفات المتاحة: {', '.join(list_profiles())}", chat_id)
            return True

        return False
