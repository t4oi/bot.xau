"""Command handler — dispatches Telegram text commands and callbacks."""
from __future__ import annotations
from typing import Any, Callable, Dict, Optional

from core.logging_config import get_logger
from core.utils import format_price
from .client import TelegramClient
from .formatter import SignalFormatter
from .keyboards import KeyboardFactory

logger = get_logger("telegram.handlers")


class CommandHandler:
    """Routes incoming Telegram messages/callbacks to actions."""

    def __init__(self, client: TelegramClient, bot_state: Optional[Any] = None,
                 monitor=None, repository=None, scan_loop=None):
        self.client = client
        self.formatter = SignalFormatter()
        self.keyboards = KeyboardFactory()
        self.bot_state = bot_state
        self.monitor = monitor
        self.repo = repository
        self.scan_loop = scan_loop
        self._callbacks: Dict[str, Callable] = {}
        # Register inline-button callbacks
        self.register_callback("enter", self._cb_enter)
        self.register_callback("skip", self._cb_skip)
        self.register_callback("be", self._cb_be)
        self.register_callback("close", self._cb_close)

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
    # Inline button callbacks
    # ------------------------------------------------------------------
    def _find_signal_in_memory(self, signal_id: str):
        if not self.scan_loop:
            return None
        for sig in getattr(self.scan_loop.state, "recent_signals", []):
            if getattr(sig, "id", None) == signal_id:
                return sig
        return None

    def _ensure_monitored(self, signal_id: str) -> Optional[Dict]:
        """Ensure signal is tracked by the monitor; return its state."""
        if not self.monitor:
            return None
        state = self.monitor.get_state(signal_id)
        if state:
            return state
        # Try in-memory signal
        sig = self._find_signal_in_memory(signal_id)
        if sig:
            self.monitor.add_signal(sig)
            return self.monitor.get_state(signal_id)
        # Try DB record
        if self.repo:
            for rec in self.repo.recent_signals(limit=50):
                if rec.signal_id == signal_id:
                    self.monitor.add_from_record(rec)
                    return self.monitor.get_state(signal_id)
        return None

    def _cb_enter(self, chat_id: str, signal_id: str) -> None:
        state = self._ensure_monitored(signal_id)
        if state:
            dir_label = "شراء" if state["direction"] == "BUY" else "بيع"
            self.client.send_message(
                f"✅ <b>تم تأكيد الدخول</b>\n"
                f"🔖 ID: <code>{signal_id}</code>\n"
                f"📊 {state['symbol']} — {dir_label} @ {format_price(state['entry'])}\n"
                f"👁 سأتابع الصفقة وأنبّهك عند تحقق TP1 / TP2 / TP3 أو ضرب الستوب.",
                chat_id,
            )
        else:
            self.client.send_message(
                f"⚠️ لم أتمكن من إيجاد الإشارة <code>{signal_id}</code>.", chat_id)

    def _cb_skip(self, chat_id: str, signal_id: str) -> None:
        if self.monitor:
            self.monitor.close_signal(signal_id, reason="SKIPPED")
        self.client.send_message(
            f"⏭ تم تخطي الإشارة <code>{signal_id}</code>.", chat_id)

    def _cb_be(self, chat_id: str, signal_id: str) -> None:
        self._ensure_monitored(signal_id)
        if self.monitor and self.monitor.move_to_breakeven(signal_id):
            self.client.send_message(
                f"🛡 <b>تم نقل الستوب لوس إلى البريك إيفن</b>\n"
                f"🔖 ID: <code>{signal_id}</code>\n"
                f"الصفقة الآن مضمونة (بدون خسارة).",
                chat_id,
            )
        else:
            self.client.send_message(
                f"ℹ️ الستوب عند البريك إيفن بالفعل أو الإشارة غير متاحة <code>{signal_id}</code>.",
                chat_id)

    def _cb_close(self, chat_id: str, signal_id: str) -> None:
        state = self._ensure_monitored(signal_id)
        price = 0.0
        try:
            if self.scan_loop and self.scan_loop.state.feed:
                tick = self.scan_loop.state.feed.tick(force_refresh=True)
                price = tick.mid if tick else 0.0
        except Exception:
            price = 0.0
        if self.monitor:
            self.monitor.close_signal(signal_id, reason="MANUAL_CLOSE")
        price_line = f"💹 السعر الحالي: <b>{format_price(price)}</b>\n" if price > 0 else ""
        self.client.send_message(
            f"🔒 <b>تم إغلاق الصفقة يدوياً</b>\n"
            f"🔖 ID: <code>{signal_id}</code>\n"
            f"{price_line}"
            f"تم إيقاف متابعة الإشارة.",
            chat_id,
        )

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------
    def _handle_price(self, chat_id: str) -> None:
        feed = getattr(self.scan_loop.state, "feed", None) if self.scan_loop else getattr(self.bot_state, "feed", None)
        if not feed:
            self.client.send_message("⚠️ حالة البوت غير متاحة.", chat_id)
            return
        try:
            tick = feed.tick()
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
        signals = []
        if self.scan_loop and hasattr(self.scan_loop.state, "recent_signals"):
            signals = self.scan_loop.state.recent_signals[-5:]
        elif self.bot_state and hasattr(self.bot_state, "recent_signals"):
            signals = self.bot_state.recent_signals[-5:]
        if not signals:
            self.client.send_message("لا توجد إشارات حديثة.", chat_id)
            return
        for sig in signals:
            self.client.send_message(self.formatter.format_signal(sig), chat_id)

    def _handle_status(self, chat_id: str) -> None:
        stats = {}
        if self.repo:
            try:
                stats = self.repo.daily_stats()
            except Exception:
                stats = {}
        if self.monitor:
            stats["open_monitored"] = self.monitor.active_count()
        self.client.send_message(self.formatter.format_daily_report(stats), chat_id)
