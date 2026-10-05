"""Multi-timeframe confluence — aggregates votes across timeframes & strategies."""
from __future__ import annotations
from typing import Dict, List, Optional

from ..config.constants import SignalDirection, Timeframe
from ..core.logging_config import get_logger
from ..data.base import Candle
from .base import Strategy, StrategyResult, SignalVote
from .registry import get_registry

logger = get_logger("strategies.mtf")


class MultiTimeframeConfluence:
    """Runs all enabled strategies on all timeframes and aggregates votes."""

    def __init__(self, enabled_strategies: Optional[List[str]] = None,
                 timeframes: Optional[List[str]] = None):
        self.registry = get_registry()
        self.strategies = self.registry.create_all(enabled_strategies)
        self.timeframes = timeframes or ["5m", "15m", "1h", "4h"]

    def scan(self, candles_by_tf: Dict[str, List[Candle]]) -> Dict[str, List[SignalVote]]:
        """Run every strategy on every timeframe. Returns {tf: [votes]}."""
        votes_by_tf: Dict[str, List[SignalVote]] = {}
        for tf in self.timeframes:
            candles = candles_by_tf.get(tf, [])
            if not candles:
                continue
            tf_votes: List[SignalVote] = []
            for strat in self.strategies:
                try:
                    result: StrategyResult = strat.analyze(candles, timeframe=tf)
                    for vote in result.votes:
                        vote.timeframe = tf
                        tf_votes.append(vote)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Strategy %s failed on %s: %s", strat.name, tf, exc)
            votes_by_tf[tf] = tf_votes
        return votes_by_tf

    def weighted_score(self, votes_by_tf: Dict[str, List[SignalVote]]) -> Dict[str, float]:
        """Compute weighted net score per timeframe."""
        scores: Dict[str, float] = {}
        for tf, votes in votes_by_tf.items():
            weight = getattr(Timeframe(tf), "weight", 1.0) if tf in Timeframe._value2member_map_ else 1.0
            net = sum(v.signed_score for v in votes) * weight
            scores[tf] = net
        return scores

    def overall_direction(self, votes_by_tf: Dict[str, List[SignalVote]]) -> SignalDirection:
        scores = self.weighted_score(votes_by_tf)
        total = sum(scores.values())
        if total > 30:
            return SignalDirection.BUY
        if total < -30:
            return SignalDirection.SELL
        return SignalDirection.NEUTRAL

    def confidence_pct(self, votes_by_tf: Dict[str, List[SignalVote]]) -> float:
        scores = self.weighted_score(votes_by_tf)
        total_abs = sum(abs(s) for s in scores.values())
        if total_abs == 0:
            return 0.0
        total = sum(scores.values())
        return min(100.0, abs(total) / total_abs * 100.0)
