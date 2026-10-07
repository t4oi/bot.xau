"""Signal message formatter — beautiful HTML messages for Telegram."""
from __future__ import annotations
from typing import List

from config.constants import SignalDirection, SignalStrength
from core.utils import format_price, format_pct
from signals.generator import TradingSignal


class SignalFormatter:
    """Renders TradingSignal objects into Telegram HTML."""

    STRENGTH_EMOJI = {
        SignalStrength.WEAK: "⚪",
        SignalStrength.MODERATE: "🟡",
        SignalStrength.STRONG: "🟠",
        SignalStrength.VERY_STRONG: "🔴",
    }

    @staticmethod
    def direction_emoji(direction: SignalDirection) -> str:
        return "🟢 BUY" if direction == SignalDirection.BUY else "🔴 SELL"

    def format_signal(self, signal: TradingSignal, lot_size: float = 0.0) -> str:
        dir_label = self.direction_emoji(signal.direction)
        strength = self.STRENGTH_EMOJI.get(signal.strength, "⚪")
        tps = "\n".join(
            f"   🎯 TP{i+1}: <b>{format_price(tp)}</b>"
            for i, tp in enumerate(signal.take_profits)
        )
        reasons = "\n".join(f"   • {r}" for r in signal.reasons[:6])

        lot_line = f"\n💰 حجم مقترح: <b>{lot_size:.2f} لوت</b>" if lot_size > 0 else ""

        return (
            f"{'='*30}\n"
            f"📊 <b>إشارة تداول — {signal.symbol}</b>\n"
            f"{'='*30}\n\n"
            f"{dir_label}  {strength} <b>{signal.strength.value.replace('_',' ')}</b>\n"
            f"⏱ الفريم: <b>{signal.timeframe}</b>\n"
            f"📈 نسبة التقاء: <b>{signal.confluence_pct:.1f}%</b>\n"
            f"⚖️ نسبة المخاطرة للعائد: <b>1:{signal.risk_reward:.1f}</b>\n\n"
            f"💎 الدخول: <b>{format_price(signal.entry)}</b>\n"
            f"🛑 الستوب لوس: <b>{format_price(signal.stop_loss)}</b>\n"
            f"{tps}\n"
            f"{lot_line}\n"
            f"📋 <b>الأسباب:</b>\n{reasons}\n\n"
            f"🌍 الجلسة: {signal.session}\n"
            f"💹 السبريد: {signal.spread:.2f} | ATR: {signal.atr:.2f}\n"
            f"🕐 {signal.created_at}\n"
            f"🔖 ID: <code>{signal.id}</code>\n\n"
            f"<i>⚠️ هذه إشارة تحليلية وليست نصيحة استثمارية.</i>\n"
            f"{'='*30}"
        )

    def format_from_record(self, rec) -> str:
        """Format a persisted SignalRecord (for re-sending undelivered signals)."""
        dir_label = "🟢 BUY" if (rec.direction or "").upper() == "BUY" else "🔴 SELL"
        try:
            tps = [float(x) for x in (rec.take_profits or "").split(",") if x.strip()]
        except Exception:
            tps = []
        tp_lines = "\n".join(
            f"   🎯 TP{i+1}: <b>{format_price(tp)}</b>" for i, tp in enumerate(tps)
        )
        strength = rec.strength or "MODERATE"
        created = rec.created_at.isoformat() if hasattr(rec.created_at, "isoformat") else str(rec.created_at)
        return (
            f"{'='*30}\n"
            f"📊 <b>إشارة تداول — {rec.symbol}</b> <i>(إعادة إرسال)</i>\n"
            f"{'='*30}\n\n"
            f"{dir_label}  <b>{strength.replace('_',' ')}</b>\n"
            f"⏱ الفريم: <b>{rec.timeframe}</b>\n"
            f"📈 نسبة التقاء: <b>{rec.confluence_pct:.1f}%</b>\n"
            f"⚖️ نسبة المخاطرة للعائد: <b>1:{rec.risk_reward:.1f}</b>\n\n"
            f"💎 الدخول: <b>{format_price(rec.entry)}</b>\n"
            f"🛑 الستوب لوس: <b>{format_price(rec.stop_loss)}</b>\n"
            f"{tp_lines}\n\n"
            f"🌍 الجلسة: {rec.session or ''}\n"
            f"💹 ATR: {rec.atr:.2f}\n"
            f"🕐 {created}\n"
            f"🔖 ID: <code>{rec.signal_id}</code>\n\n"
            f"<i>⚠️ هذه إشارة تحليلية وليست نصيحة استثمارية.</i>\n"
            f"{'='*30}"
        )

    def format_price_alert(self, symbol: str, price: float, change_pct: float,
                           high: float, low: float, spread: float) -> str:
        arrow = "📈" if change_pct >= 0 else "📉"
        return (
            f"💹 <b>{symbol} — السعر المباشر</b>\n\n"
            f"{arrow} السعر: <b>{format_price(price)}</b> ({format_pct(change_pct)})\n"
            f"🔺 أعلى اليوم: {format_price(high)}\n"
            f"🔻 أدنى اليوم: {format_price(low)}\n"
            f"📏 السبريد: {spread:.2f}\n"
        )

    def format_daily_report(self, stats: dict) -> str:
        return (
            f"📊 <b>تقرير أداء اليوم</b>\n\n"
            f"📨 إشارات مرسلة: <b>{stats.get('signals_sent', 0)}</b>\n"
            f"✅ صفقات رابحة: <b>{stats.get('wins', 0)}</b>\n"
            f"❌ صفقات خاسرة: <b>{stats.get('losses', 0)}</b>\n"
            f"🎯 نسبة النجاح: <b>{stats.get('win_rate', 0):.1f}%</b>\n"
            f"💰 صافي الربح: <b>${stats.get('pnl', 0):.2f}</b>\n"
            f"📉 أكبر سحب: <b>{stats.get('max_dd', 0):.1f}%</b>\n"
        )

    def format_help(self) -> str:
        return (
            f"🤖 <b>XAUUSD Pro Signal Bot</b>\n\n"
            f"<b>الأوامر المتاحة:</b>\n"
            f"/start — قائمة رئيسية\n"
            f"/price — سعر XAUUSD الحالي\n"
            f"/signals — آخر الإشارات\n"
            f"/status — حالة البوت\n"
            f"/performance — تقرير الأداء\n"
            f"/settings — الإعدادات\n"
            f"/help — هذه المساعدة\n"
        )
