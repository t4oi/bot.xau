"""Keyboard factory — inline and reply keyboards for Telegram."""
from __future__ import annotations
from typing import Dict, List


class KeyboardFactory:
    """Builds Telegram reply_markup objects."""

    @staticmethod
    def main_menu() -> Dict:
        return {
            "keyboard": [
                [{"text": "📊 سعر XAUUSD"}, {"text": "📨 آخر الإشارات"}],
                [{"text": "📈 الأداء"}, {"text": "⚙️ الإعدادات"}],
                [{"text": "🆔 Chat ID"}, {"text": "❓ المساعدة"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }

    @staticmethod
    def signal_actions(signal_id: str) -> Dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ تأكيد الدخول", "callback_data": f"enter:{signal_id}"},
                    {"text": "⏭ تخطي", "callback_data": f"skip:{signal_id}"},
                ],
                [
                    {"text": "🛑 نقل للبريك إيفن", "callback_data": f"be:{signal_id}"},
                    {"text": "🔒 إغلاق", "callback_data": f"close:{signal_id}"},
                ],
            ]
        }

    @staticmethod
    def timeframe_selector() -> Dict:
        return {
            "inline_keyboard": [
                [{"text": tf, "callback_data": f"tf:{tf}"} for tf in ["1m", "5m", "15m"]],
                [{"text": tf, "callback_data": f"tf:{tf}"} for tf in ["30m", "1h", "4h"]],
            ]
        }

    @staticmethod
    def settings_menu() -> Dict:
        return {
            "inline_keyboard": [
                [{"text": "🎚 نسبة المخاطرة", "callback_data": "set:risk"}],
                [{"text": "⏱ فترة الفحص", "callback_data": "set:interval"}],
                [{"text": "🔔 تفعيل/إيقاف الإشارات", "callback_data": "set:toggle"}],
                [{"text": "📊 الحد الأدنى للتقاء", "callback_data": "set:confluence"}],
            ]
        }

    @staticmethod
    def remove_keyboard() -> Dict:
        return {"remove_keyboard": True}
