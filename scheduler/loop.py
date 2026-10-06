"""Main scan loop — orchestrates the full signal pipeline on a timer."""
from __future__ import annotations
import threading
import time
from typing import Dict, List, Optional

from config.settings import get_settings
from core.logging_config import get_logger
from data.base import Candle
from data.feed import FeedManager
from risk.limits import RiskLimits
from risk.position_sizer import PositionSizer
from signals.generator import SignalGenerator, TradingSignal
from strategies.multi_tf_confluence import MultiTimeframeConfluence
from telegram_bot.client import TelegramClient
from telegram_bot.formatter import SignalFormatter
from telegram_bot.keyboards import KeyboardFactory

logger = get_logger("scheduler.loop")


class BotState:
    """Shared mutable state across the bot."""

    def __init__(self):
        self.recent_signals: List[TradingSignal] = []
        self.daily_stats: dict = {}
        self.running = False
        self.last_scan = 0.0
        self.feed: Optional[FeedManager] = None


class ScanLoop:
    """The main loop: fetch -> analyze -> signal -> filter -> deliver -> persist."""

    def __init__(self,
                 feed: FeedManager,
                 mtf: MultiTimeframeConfluence,
                 generator: SignalGenerator,
                 telegram: TelegramClient,
                 risk_limits: RiskLimits,
                 position_sizer: PositionSizer,
                 repository=None,
                 interval_seconds: int = 60):
        self.feed = feed
        self.mtf = mtf
        self.generator = generator
        self.telegram = telegram
        self.risk_limits = risk_limits
        self.position_sizer = position_sizer
        self.repo = repository
        self.interval = interval_seconds
        self.state = BotState()
        self.state.feed = feed
        self.formatter = SignalFormatter()
        self.keyboards = KeyboardFactory()
        self._thread: Optional[threading.Thread] = None

    def scan_once(self) -> Optional[TradingSignal]:
        """One full scan cycle. Returns the signal if one was generated & sent."""
        settings = get_settings()
        logger.info("Starting scan cycle...")
        self.state.last_scan = time.time()  # fix: update even when no signal

        # 1. Risk gate
        allowed, reason = self.risk_limits.can_trade()
        if not allowed:
            logger.info("Trading blocked: %s", reason)
            return None

        # 2. Fetch multi-timeframe candles
        candles_by_tf: Dict[str, List[Candle]] = self.feed.multi_timeframe(
            settings.timeframe_list, limit=500
        )
        if not any(candles_by_tf.values()):
            logger.warning("No candle data available")
            return None

        # 3. Run all strategies on all timeframes
        votes_by_tf = self.mtf.scan(candles_by_tf)
        all_votes = [v for votes in votes_by_tf.values() for v in votes]
        logger.info("Collected %d votes across %d timeframes",
                    len(all_votes), len(votes_by_tf))

        # 4. Generate signal (includes confluence + TP/SL + filters)
        primary_candles = candles_by_tf.get(settings.primary_timeframe, [])
        tick = self.feed.tick()
        signal = self.generator.generate(
            all_votes, primary_candles, tick=tick,
            primary_tf=settings.primary_timeframe, symbol=settings.trading_symbol,
            num_tps=settings.default_take_profits,
        )

        if not signal:
            logger.info("No signal this cycle.")
            return None

        # 5. Position sizing
        sizing = self.position_sizer.calculate(signal.entry, signal.stop_loss)

        # 6. Deliver to Telegram
        message = self.formatter.format_signal(signal, lot_size=sizing.lot_size)
        sent = self.telegram.send_message(
            message, reply_markup=self.keyboards.signal_actions(signal.id),
        )
        logger.info("Signal %s delivered: %s", signal.id, sent)

        # 7. Persist
        self.risk_limits.record_signal()
        if self.repo:
            try:
                self.repo.save_signal(signal)
            except Exception as exc:  # noqa: BLE001
                logger.warning("DB save failed: %s", exc)

        self.state.recent_signals.append(signal)
        if len(self.state.recent_signals) > 50:
            self.state.recent_signals = self.state.recent_signals[-50:]
        self.state.last_scan = time.time()
        return signal

    def _run_forever(self) -> None:
        self.state.running = True
        while self.state.running:
            try:
                self.scan_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scan cycle failed: %s", exc)
            time.sleep(self.interval)

    def start(self, blocking: bool = False) -> None:
        if blocking:
            self._run_forever()
        else:
            self._thread = threading.Thread(target=self._run_forever, daemon=True)
            self._thread.start()
            logger.info("Scan loop started in background (interval %ds)", self.interval)

    def stop(self) -> None:
        self.state.running = False
        if self._thread:
            self._thread.join(timeout=10)
