"""Signal generator — the main orchestrator that produces TradingSignal objects."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config.constants import SignalDirection, SignalStrength, DEFAULT_SYMBOL
from core.logging_config import get_logger
from core.utils import now_iso, round_price
from data.base import Candle, Tick
from strategies.base import SignalVote
from .confluence_scorer import ConfluenceScorer
from .filters import SignalFilter
from .tp_sl_calculator import TpSlCalculator

logger = get_logger("signal.generator")


@dataclass
class TradingSignal:
    """A fully-formed trading signal ready for delivery."""
    id: str
    symbol: str
    direction: SignalDirection
    strength: SignalStrength
    entry: float
    stop_loss: float
    take_profits: List[float]
    risk_reward: float
    confluence_pct: float
    timeframe: str
    reasons: List[str] = field(default_factory=list)
    votes: List[SignalVote] = field(default_factory=list)
    atr: float = 0.0
    spread: float = 0.0
    session: str = ""
    created_at: str = ""
    extra: Dict = field(default_factory=dict)

    @property
    def is_buy(self) -> bool:
        return self.direction == SignalDirection.BUY

    @property
    def is_sell(self) -> bool:
        return self.direction == SignalDirection.SELL


class SignalGenerator:
    """Orchestrates strategies -> votes -> confluence -> TP/SL -> filters."""

    def __init__(self,
                 scorer: Optional[ConfluenceScorer] = None,
                 calculator: Optional[TpSlCalculator] = None,
                 signal_filter: Optional[SignalFilter] = None,
                 min_confluence: float = 60.0):
        self.scorer = scorer or ConfluenceScorer()
        self.calculator = calculator or TpSlCalculator()
        self.filter = signal_filter or SignalFilter(min_confluence=min_confluence)
        self.min_confluence = min_confluence

    def generate(self,
                 votes: List[SignalVote],
                 candles: List[Candle],
                 tick: Optional[Tick] = None,
                 primary_tf: str = "15m",
                 symbol: str = DEFAULT_SYMBOL,
                 num_tps: int = 3) -> Optional[TradingSignal]:
        """Produce a signal, or None if filtered out."""
        if not votes:
            return None

        score = self.scorer.score(votes)
        direction = score["direction"]
        confluence = score["score_pct"]

        if direction == SignalDirection.NEUTRAL:
            logger.info("Neutral confluence, no signal.")
            return None

        current_price = tick.mid if tick and tick.mid > 0 else (candles[-1].close if candles else 0)
        if current_price <= 0:
            return None

        tp_sl = self.calculator.compute(candles, direction, current_price, num_tps=num_tps)
        spread = tick.spread if tick else 0.0

        filter_result = self.filter.apply_all(
            spread=spread, rr=tp_sl["risk_reward_tp1"],
            confluence=confluence, symbol=symbol,
        )

        if not filter_result["passed"]:
            logger.info("Signal filtered out: %s", filter_result["reasons"])
            return None

        # Determine strength
        if confluence >= 80:
            strength = SignalStrength.VERY_STRONG
        elif confluence >= 70:
            strength = SignalStrength.STRONG
        elif confluence >= 60:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Top reasons from agreeing votes
        reasons: List[str] = []
        for v in score["agreeing"][:8]:
            reasons.extend([r for r in v.reasons if r and r not in reasons][:2])

        signal = TradingSignal(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            direction=direction,
            strength=strength,
            entry=tp_sl["entry"],
            stop_loss=tp_sl["stop_loss"],
            take_profits=tp_sl["take_profits"],
            risk_reward=tp_sl["risk_reward_tp1"],
            confluence_pct=confluence,
            timeframe=primary_tf,
            reasons=reasons[:10],
            votes=votes,
            atr=tp_sl["atr"],
            spread=spread,
            session=filter_result.get("session", ""),
            created_at=now_iso(),
            extra={
                "raw_score": score["raw_score"],
                "by_strategy": score["by_strategy"],
                "by_timeframe": score["by_timeframe"],
                "fibonacci": tp_sl["fibonacci_extensions"],
                "filter_reasons": filter_result["reasons"],
            },
        )

        self.filter.mark_sent(symbol)
        logger.info("Generated %s signal %s @ %.2f (conf %.1f%%)",
                    direction.value, signal.id, signal.entry, confluence)
        return signal
