"""Confluence scorer — aggregates strategy votes into a unified score."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

from ..config.constants import SignalDirection, Timeframe
from ..strategies.base import SignalVote


class ConfluenceScorer:
    """Weighted aggregation of votes across strategies and timeframes."""

    def __init__(self, tf_weights: Dict[str, float] = None):
        self.tf_weights = tf_weights or {
            "1m": 0.5, "5m": 0.7, "15m": 1.0, "30m": 1.2,
            "1h": 1.5, "4h": 2.0, "1d": 2.5,
        }

    def score(self, votes: List[SignalVote]) -> Dict:
        """Return {direction, score_pct, by_strategy, by_timeframe, agreeing, opposing}."""
        if not votes:
            return {"direction": SignalDirection.NEUTRAL, "score_pct": 0.0,
                    "by_strategy": {}, "by_timeframe": {}, "agreeing": [], "opposing": []}

        by_strategy: Dict[str, float] = defaultdict(float)
        by_tf: Dict[str, float] = defaultdict(float)
        total_weighted = 0.0
        total_abs = 0.0

        for v in votes:
            w = self.tf_weights.get(v.timeframe, 1.0)
            signed = v.signed_score * w
            by_strategy[v.strategy] += signed
            by_tf[v.timeframe] += signed
            total_weighted += signed
            total_abs += abs(signed)

        score_pct = (abs(total_weighted) / total_abs * 100.0) if total_abs > 0 else 0.0
        direction = (SignalDirection.BUY if total_weighted > 0
                     else SignalDirection.SELL if total_weighted < 0
                     else SignalDirection.NEUTRAL)

        agreeing = [v for v in votes if
                    (direction == SignalDirection.BUY and v.direction == SignalDirection.BUY) or
                    (direction == SignalDirection.SELL and v.direction == SignalDirection.SELL)]
        opposing = [v for v in votes if
                    (direction == SignalDirection.BUY and v.direction == SignalDirection.SELL) or
                    (direction == SignalDirection.SELL and v.direction == SignalDirection.BUY)]

        return {
            "direction": direction,
            "score_pct": round(score_pct, 1),
            "raw_score": round(total_weighted, 1),
            "by_strategy": dict(by_strategy),
            "by_timeframe": dict(by_tf),
            "agreeing": agreeing,
            "opposing": opposing,
            "total_votes": len(votes),
        }

    def trend_alignment(self, votes_by_tf: Dict[str, List[SignalVote]]) -> float:
        """0..1 — fraction of timeframes agreeing on direction."""
        if not votes_by_tf:
            return 0.0
        directions = []
        for tf, vlist in votes_by_tf.items():
            net = sum(v.signed_score for v in vlist)
            if net > 5:
                directions.append(1)
            elif net < -5:
                directions.append(-1)
            else:
                directions.append(0)
        nonzero = [d for d in directions if d != 0]
        if not nonzero:
            return 0.0
        majority = 1 if sum(nonzero) > 0 else -1
        return sum(1 for d in nonzero if d == majority) / len(nonzero)
