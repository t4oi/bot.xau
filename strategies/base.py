"""Base classes for all strategies."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.constants import SignalDirection
from data.base import Candle


@dataclass
class SignalVote:
    """A single strategy's opinion on the market."""
    strategy: str
    direction: SignalDirection
    confidence: float          # 0..100
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timeframe: str = ""
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def signed_score(self) -> float:
        if self.direction == SignalDirection.BUY:
            return self.confidence
        if self.direction == SignalDirection.SELL:
            return -self.confidence
        return 0.0


@dataclass
class StrategyResult:
    """Aggregated result from one strategy."""
    strategy: str
    votes: List[SignalVote] = field(default_factory=list)
    raw_indicators: Dict[str, Any] = field(default_factory=dict)

    @property
    def net_direction(self) -> SignalDirection:
        if not self.votes:
            return SignalDirection.NEUTRAL
        total = sum(v.signed_score for v in self.votes)
        if total > 15:
            return SignalDirection.BUY
        if total < -15:
            return SignalDirection.SELL
        return SignalDirection.NEUTRAL

    @property
    def avg_confidence(self) -> float:
        if not self.votes:
            return 0.0
        return sum(abs(v.signed_score) for v in self.votes) / len(self.votes)


class Strategy(ABC):
    """Abstract strategy. Subclasses implement analyze()."""

    name: str = "base_strategy"
    description: str = ""
    default_timeframes: List[str] = ["15m", "1h"]

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}

    @abstractmethod
    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        """Analyze candles and return votes."""

    def vote_buy(self, confidence: float, reasons: Optional[List[str]] = None,
                 **kwargs: Any) -> SignalVote:
        return SignalVote(
            strategy=self.name, direction=SignalDirection.BUY,
            confidence=confidence, reasons=reasons or [], metadata=kwargs,
        )

    def vote_sell(self, confidence: float, reasons: Optional[List[str]] = None,
                  **kwargs: Any) -> SignalVote:
        return SignalVote(
            strategy=self.name, direction=SignalDirection.SELL,
            confidence=confidence, reasons=reasons or [], metadata=kwargs,
        )

    def vote_neutral(self, reasons: Optional[List[str]] = None, **kwargs: Any) -> SignalVote:
        return SignalVote(
            strategy=self.name, direction=SignalDirection.NEUTRAL,
            confidence=0.0, reasons=reasons or [], metadata=kwargs,
        )

    def __repr__(self) -> str:
        return f"<Strategy {self.name} params={self.params}>"
