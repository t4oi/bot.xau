"""Command handler — dispatches Telegram text commands and callbacks."""
from __future__ import annotations
from typing import Any, Callable, Dict, Optional

from core.logging_config import get_logger
from .client import TelegramClient
from .formatter import SignalFormatter
from .keyboards import KeyboardFactory

logger = get_logger("telegram.handlers")


class CommandHandler:
    """Routes incoming Telegram messages/callbacks to actions."""

    def __init__(self, client: TelegramClient, bot_state: Optional[Any] = None):
        self.client = client
        self.formatter = SignalFormatter()
        self.keyboards = KeyboardFactory()
        self.bot_state = bot_state
        self._callbacks: Dict[str, Callable] = {}

    def register_callback(self, prefix: str, fn: Callable) -> None:
        self._callbacks[prefix] = fn

    def handle(self, chat_id: str, text: str) -> None:
        """Handle a text message/command."""
        text = (text or "").strip()
        logger.info("Command from %s: %s", chat_id, text[:50])

        if text in ("/start", "start", "🏠 الرئيسية"):
            self.client.send_message(
                "🤖 أهلاً بك في <b>XAUUSD Pro Signal Bot</b>\nاختر من القائمة بالأسفل 👇",
                chat_id, reply_markup=self.keyboards.main_menu(),
            )
        elif text in ("/price", "📊 سعر XAUUSD", "سعر"):
            self._handle_price(chat_id)
        elif text in ("/signals", "📨 آخر الإشارات", "الإشارات"):
            self._handle_signals(chat_id)
        elif text in ("/status", "/performance", "📈 الأداء", "الحالة"):
            self._handle_status(chat_id)
        elif text in ("/settings", "⚙️ الإعدادات"):
            self.client.send_message("⚙️ الإعدادات:", chat_id,
                                     reply_markup=self.keyboards.settings_menu())
        elif text in ("/help", "❓ المساعدة"):
            self.client.send_message(self.formatter.format_help(), chat_id)
        elif text in ("/id", "🆔 Chat ID"):
            self.client.send_message(f"🆔 Chat ID الخاص بك:\n<code>{chat_id}</code>", chat_id)
        else:
            self.client.send_message(
                "❓ لم أفهم الأمر. استخدم /help لعرض الأوامر المتاحة.", chat_id,
                reply_markup=self.keyboards.main_menu(),
            )

    def handle_callback(self, chat_id: str, data: str) -> None:
        """Handle inline button callback."""
        if ":" not in data:
            return
        prefix, payload = data.split(":", 1)
        handler = self._callbacks.get(prefix)
        if handler:
            try:
                handler(chat_id, payload)
            except Exception as exc:  # noqa: BLE001
                logger.error("Callback handler %s failed: %s", prefix, exc)
                self.client.send_message("⚠️ حدث خطأ في معالجة الطلب.", chat_id)
        else:
            logger.info("Unhandled callback prefix: %s", prefix)

    # ------------------------------------------------------------------
    def _handle_price(self, chat_id: str) -> None:
        if not self.bot_state:
            self.client.send_message("⚠️ حالة البوت غير متاحة.", chat_id)
            return
        try:
            tick = self.bot_state.feed.tick()
            if tick:
                self.client.send_message(
                    self.formatter.format_price_alert(
                        tick.symbol, tick.mid, tick.day_diff_pct, tick.high, tick.low, tick.spread),
                    chat_id,
                )
            else:
                self.client.send_message("⚠️ تعذر جلب السعر حالياً.", chat_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Price fetch failed: %s", exc)
            self.client.send_message("⚠️ تعذر جلب السعر.", chat_id)

    def _handle_signals(self, chat_id: str) -> None:
        if not self.bot_state or not hasattr(self.bot_state, "recent_signals"):
            self.client.send_message("لا توجد إشارات مسجلة بعد.", chat_id)
            return
        signals = self.bot_state.recent_signals[-5:]
        if not signals:
            self.client.send_message("لا توجد إشارات حديثة.", chat_id)
            return
        for sig in signals:
            self.client.send_message(self.formatter.format_signal(sig), chat_id)

    def _handle_status(self, chat_id: str) -> None:
        if not self.bot_state:
            self.client.send_message("⚠️ حالة البوت غير متاحة.", chat_id)
            return
        stats = getattr(self.bot_state, "daily_stats", {})
        self.client.send_message(self.formatter.format_daily_report(stats), chat_id)
