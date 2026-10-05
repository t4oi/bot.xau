"""Ensemble meta-strategy — weighted voting across all strategies with dynamic weights."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

from ..config.constants import SignalDirection
from ..core.logging_config import get_logger
from ..data.base import Candle
from .base import Strategy, StrategyResult, SignalVote
from .registry import get_registry

logger = get_logger("strategies.ensemble")


class EnsembleStrategy(Strategy):
    """Meta-strategy that combines all registered strategies with performance-based weights."""

    name = "ensemble"
    description = "Weighted ensemble of all strategies with dynamic performance weighting."

    def __init__(self, params: Dict = None):
        super().__init__(params)
        self.registry = get_registry()
        self.strategies = self.registry.create_all()
        # Dynamic weights updated by recent performance
        self.weights: Dict[str, float] = {s.name: 1.0 for s in self.strategies}
        self.performance: Dict[str, List[float]] = defaultdict(list)

    def update_weight(self, strategy_name: str, pnl: float) -> None:
        """Update a strategy's weight based on a trade result."""
        self.performance[strategy_name].append(pnl)
        recent = self.performance[strategy_name][-20:]
        avg = sum(recent) / len(recent) if recent else 0
        self.weights[strategy_name] = max(0.1, 1.0 + avg * 0.01)
        logger.debug("Weight %s -> %.2f", strategy_name, self.weights[strategy_name])

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        all_votes: List[SignalVote] = []
        raw: Dict[str, float] = defaultdict(float)

        for strat in self.strategies:
            try:
                strat_result = strat.analyze(candles, timeframe)
                weight = self.weights.get(strat.name, 1.0)
                for vote in strat_result.votes:
                    weighted = SignalVote(
                        strategy=f"ens_{vote.strategy}",
                        direction=vote.direction,
                        confidence=vote.confidence * weight,
                        timeframe=timeframe,
                        reasons=vote.reasons,
                    )
                    all_votes.append(weighted)
                    raw[strat.name] += weighted.signed_score
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ensemble: strategy %s failed: %s", strat.name, exc)

        net = sum(v.signed_score for v in all_votes)
        result.raw_indicators = dict(raw)
        result.raw_indicators["net_ensemble_score"] = net

        if net > 20:
            result.votes.append(self.vote_buy(
                min(90, 50 + abs(net) / 5),
                reasons=[f"Ensemble net score {net:.1f}",
                         f"{sum(1 for v in all_votes if v.direction == SignalDirection.BUY)} bullish votes"],
                timeframe=timeframe,
            ))
        elif net < -20:
            result.votes.append(self.vote_sell(
                min(90, 50 + abs(net) / 5),
                reasons=[f"Ensemble net score {net:.1f}",
                         f"{sum(1 for v in all_votes if v.direction == SignalDirection.SELL)} bearish votes"],
                timeframe=timeframe,
            ))
        else:
            result.votes.append(self.vote_neutral(
                reasons=[f"Ensemble mixed (net {net:.1f})"], timeframe=timeframe))

        result.votes.extend(all_votes)
        return result
