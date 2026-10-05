"""Backtesting engine — event-driven backtest with TP/SL execution."""
from .engine import BacktestEngine, BacktestTrade, BacktestResult
from .metrics import PerformanceMetrics, compute_metrics
from .walk_forward import WalkForwardAnalyzer
from .equity_curve import EquityCurve
from .report import BacktestReport

__all__ = [
    "BacktestEngine", "BacktestTrade", "BacktestResult",
    "PerformanceMetrics", "compute_metrics",
    "WalkForwardAnalyzer", "EquityCurve", "BacktestReport",
]
