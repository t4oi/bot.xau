"""Signal generation package — aggregates votes, computes entry/TP/SL, filters."""
from .confluence_scorer import ConfluenceScorer
from .tp_sl_calculator import TpSlCalculator
from .filters import SignalFilter
from .generator import SignalGenerator, TradingSignal

__all__ = [
    "ConfluenceScorer", "TpSlCalculator", "SignalFilter",
    "SignalGenerator", "TradingSignal",
]
