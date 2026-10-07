"""Signal monitor — tracks open signals and alerts on TP1/TP2/TP3/SL hits.

State is persisted in the DB key-value store (BotStateRecord) so that
restarts / Render sleeps do not lose track of active signals.
"""
from __future__ import annotations
import json
import threading
import time
from typing import Dict, List, Optional

from config.constants import SignalDirection
from core.logging_config import get_logger
from core.utils import format_price

logger = get_logger("execution.monitor")

INDEX_KEY = "mon:index"


def _sig_state_key(signal_id: str) -> str:
    return f"mon:sig:{signal_id}"


class SignalMonitor:
    """Watches confirmed/open signals and emits Telegram alerts on milestones."""

    def __init__(self, telegram, feed, repository=None, interval_seconds: int = 20):
        self.tg = telegram
        self.feed = feed
        self.repo = repository
        self.interval = max(10, int(interval_seconds))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
    def _index(self) -> List[str]:
        if not self.repo:
            return []
        raw = self.repo.get_state(INDEX_KEY, default="[]")
        try:
            return json.loads(raw)
        except Exception:
            return []

    def _save_index(self, ids: List[str]) -> None:
        if self.repo:
            self.repo.set_state(INDEX_KEY, json.dumps(ids))

    def _load(self, signal_id: str) -> Optional[Dict]:
        if not self.repo:
            return None
        raw = self.repo.get_state(_sig_state_key(signal_id), default="")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _save(self, signal_id: str, state: Dict) -> None:
        if self.repo:
            self.repo.set_state(_sig_state_key(signal_id), json.dumps(state))

    def _delete(self, signal_id: str) -> None:
        if self.repo:
            # BotStateRecord has no delete; set empty + remove from index
            self.repo.set_state(_sig_state_key(signal_id), "")
        ids = [i for i in self._index() if i != signal_id]
        self._save_index(ids)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_signal(self, signal, lot_size: float = 0.0) -> bool:
        """Start monitoring a TradingSignal. No-op if already tracked."""
        sid = signal.id
        if self._load(sid):
            return False
        state = {
            "signal_id": sid,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "entry": float(signal.entry),
            "sl": float(signal.stop_loss),
            "tps": [float(t) for t in signal.take_profits],
            "next_tp": 0,  # index of next TP to hit
            "be_moved": False,
            "status": "ACTIVE",
            "lot": float(lot_size),
            "added_at": time.time(),
        }
        with self._lock:
            self._save(sid, state)
            ids = self._index()
            if sid not in ids:
                ids.append(sid)
                self._save_index(ids)
        logger.info("Monitor: tracking signal %s (%s @ %s)", sid, state["direction"], state["entry"])
        return True

    def add_from_record(self, rec) -> bool:
        """Add a signal from a DB SignalRecord (for re-monitoring after restart)."""
        sid = rec.signal_id
        if self._load(sid):
            return False
        try:
            tps = [float(x) for x in (rec.take_profits or "").split(",") if x.strip()]
        except Exception:
            tps = []
        if not tps:
            return False
        state = {
            "signal_id": sid,
            "symbol": rec.symbol,
            "direction": rec.direction,
            "entry": float(rec.entry),
            "sl": float(rec.stop_loss),
            "tps": tps,
            "next_tp": 0,
            "be_moved": False,
            "status": "ACTIVE",
            "lot": 0.0,
            "added_at": time.time(),
        }
        with self._lock:
            self._save(sid, state)
            ids = self._index()
            if sid not in ids:
                ids.append(sid)
                self._save_index(ids)
        return True

    def close_signal(self, signal_id: str, reason: str = "MANUAL") -> Optional[Dict]:
        state = self._load(signal_id)
        if not state:
            return None
        state["status"] = "CLOSED"
        state["close_reason"] = reason
        self._save(signal_id, state)
        self._delete(signal_id)
        return state

    def move_to_breakeven(self, signal_id: str) -> bool:
        state = self._load(signal_id)
        if not state or state.get("be_moved"):
            return False
        state["sl"] = state["entry"]
        state["be_moved"] = True
        self._save(signal_id, state)
        return True

    def get_state(self, signal_id: str) -> Optional[Dict]:
        return self._load(signal_id)

    def active_count(self) -> int:
        return len(self._index())

    # ------------------------------------------------------------------
    # Alert messages
    # ------------------------------------------------------------------
    def _alert_tps(self, state: Dict, hit_indices: List[int], price: float) -> None:
        """One combined alert for one or more TPs hit in the same cycle."""
        if not hit_indices:
            return
        dir_label = "شراء" if state["direction"] == "BUY" else "بيع"
        tp_list = "\n".join(
            f"   ✅ TP{i+1}: <b>{format_price(state['tps'][i])}</b>" for i in hit_indices
        )
        be_note = ""
        if 0 in hit_indices and not state.get("be_moved"):
            state["sl"] = state["entry"]
            state["be_moved"] = True
            be_note = "\n🛡 <b>تم نقل الستوب لوس إلى سعر الدخول (بريك إيفن) تلقائياً.</b>"
        labels = " و ".join(f"TP{i+1}" for i in hit_indices)
        msg = (
            f"🎯 <b>تحقق الهدف {labels}</b>\n"
            f"{'='*30}\n"
            f"📊 {state['symbol']} — {dir_label}\n"
            f"{tp_list}\n"
            f"💹 السعر الحالي: <b>{format_price(price)}</b>\n"
            f"💎 الدخول: {format_price(state['entry'])}\n"
            f"🛑 الستوب الحالي: <b>{format_price(state['sl'])}</b>\n"
            f"🔖 ID: <code>{state['signal_id']}</code>\n"
            f"💰 اقفل جزءاً من الصفقة واربح.\n"
            f"{be_note}"
        )
        self.tg.send_message(msg)

    def _alert_sl(self, state: Dict, price: float) -> None:
        dir_label = "شراء" if state["direction"] == "BUY" else "بيع"
        be_note = " (بريك إيفن — بدون خسارة)" if state.get("be_moved") else ""
        msg = (
            f"🛑 <b>ضرب الستوب لوس{be_note}</b>\n"
            f"{'='*30}\n"
            f"📊 {state['symbol']} — {dir_label}\n"
            f"🛑 الستوب: <b>{format_price(state['sl'])}</b>\n"
            f"💹 السعر الحالي: <b>{format_price(price)}</b>\n"
            f"💎 الدخول: {format_price(state['entry'])}\n"
            f"🔖 ID: <code>{state['signal_id']}</code>\n"
            f"📦 تم إغلاق الصفقة."
        )
        self.tg.send_message(msg)

    def _alert_final(self, state: Dict, price: float) -> None:
        dir_label = "شراء" if state["direction"] == "BUY" else "بيع"
        msg = (
            f"🏁 <b>تحقيق الهدف الأخير TP{len(state['tps'])} — إغلاق كامل</b>\n"
            f"{'='*30}\n"
            f"📊 {state['symbol']} — {dir_label}\n"
            f"💎 الدخول: {format_price(state['entry'])}\n"
            f"🎯 آخر هدف: <b>{format_price(state['tps'][-1])}</b>\n"
            f"💹 السعر الحالي: <b>{format_price(price)}</b>\n"
            f"🔖 ID: <code>{state['signal_id']}</code>\n"
            f"✅ صفقة مكتملة — مبروك!"
        )
        self.tg.send_message(msg)

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------
    def _check_one(self, state: Dict, price: float) -> None:
        sid = state["signal_id"]
        direction = state["direction"]
        is_buy = direction == "BUY"
        sl = state["sl"]
        # Stop loss check first
        sl_hit = (is_buy and price <= sl) or (not is_buy and price >= sl)
        if sl_hit:
            self._alert_sl(state, price)
            self.close_signal(sid, reason="SL")
            return
        # TP check (collect all TPs hit in this cycle, then one combined alert)
        next_idx = state.get("next_tp", 0)
        tps = state["tps"]
        hit: List[int] = []
        while next_idx < len(tps):
            tp_val = tps[next_idx]
            tp_hit = (is_buy and price >= tp_val) or (not is_buy and price <= tp_val)
            if not tp_hit:
                break
            hit.append(next_idx)
            next_idx += 1
        if hit:
            self._alert_tps(state, hit, price)
            state["next_tp"] = next_idx
            self._save(sid, state)
        if next_idx >= len(tps):
            self._alert_final(state, price)
            self.close_signal(sid, reason="TP_FINAL")
            return
        self._save(sid, state)

    def _loop(self) -> None:
        logger.info("Signal monitor started (interval=%ds)", self.interval)
        while not self._stop.is_set():
            try:
                ids = self._index()
                if ids:
                    tick = self.feed.tick(force_refresh=True)
                    price = tick.mid if tick and tick.mid > 0 else 0.0
                    if price > 0:
                        for sid in list(ids):
                            state = self._load(sid)
                            if not state or state.get("status") != "ACTIVE":
                                continue
                            try:
                                with self._lock:
                                    self._check_one(state, price)
                            except Exception as exc:  # noqa: BLE001
                                logger.error("Monitor check failed for %s: %s", sid, exc)
            except Exception as exc:  # noqa: BLE001
                logger.error("Monitor loop error: %s", exc)
            self._stop.wait(self.interval)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="signal-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
