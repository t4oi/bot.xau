"""Parameter optimizer — grid search & random search for strategy parameters."""
from __future__ import annotations
import itertools
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.logging_config import get_logger
from .engine import BacktestEngine, BacktestResult, SignalFn
from .metrics import PerformanceMetrics

logger = get_logger("backtest.optimizer")


@dataclass
class OptimizationResult:
    best_params: Dict[str, Any]
    best_metric: float
    all_results: List[Tuple[Dict[str, Any], float]]
    metric_name: str
    iterations: int


class ParameterOptimizer:
    """Grid/random search optimizer for strategy parameters."""

    def __init__(self, param_grid: Dict[str, List[Any]],
                 objective: str = "profit_factor"):
        self.param_grid = param_grid
        self.objective = objective
        self.results: List[Tuple[Dict[str, Any], float]] = []

    def _metric_value(self, metrics: PerformanceMetrics) -> float:
        mapping = {
            "profit_factor": metrics.profit_factor if metrics.profit_factor != float("inf") else 999,
            "sharpe": metrics.sharpe_ratio,
            "total_pnl": metrics.total_pnl_usd,
            "win_rate": metrics.win_rate_pct,
            "calmar": metrics.calmar_ratio if metrics.calmar_ratio != float("inf") else 999,
            "expectancy": metrics.expectancy_usd,
        }
        return mapping.get(self.objective, metrics.total_pnl_usd)

    def grid_search(self, candles, signal_fn_factory: Callable[[Dict], SignalFn],
                    initial_balance: float = 1000.0, max_evals: int = 100) -> OptimizationResult:
        keys = list(self.param_grid.keys())
        values = [self.param_grid[k] for k in keys]
        combos = list(itertools.product(*values))
        if len(combos) > max_evals:
            random.shuffle(combos)
            combos = combos[:max_evals]

        best_params, best_metric = {}, float("-inf")
        for combo in combos:
            params = dict(zip(keys, combo))
            signal_fn = signal_fn_factory(params)
            engine = BacktestEngine(initial_balance=initial_balance, warmup_bars=min(80, len(candles) // 4))
            result = engine.run(candles, signal_fn)
            metric = self._metric_value(result.metrics) if result.metrics else 0
            self.results.append((params, metric))
            if metric > best_metric and result.metrics and result.metrics.total_trades >= 5:
                best_metric = metric
                best_params = params
            logger.info("Grid eval %s -> %.3f", params, metric)

        self.results.sort(key=lambda x: x[1], reverse=True)
        return OptimizationResult(
            best_params=best_params, best_metric=round(best_metric, 3),
            all_results=self.results[:20], metric_name=self.objective,
            iterations=len(combos),
        )

    def random_search(self, candles, param_sampler: Callable[[], Dict[str, Any]],
                      signal_fn_factory: Callable[[Dict], SignalFn],
                      iterations: int = 50, initial_balance: float = 1000.0) -> OptimizationResult:
        best_params, best_metric = {}, float("-inf")
        for i in range(iterations):
            params = param_sampler()
            signal_fn = signal_fn_factory(params)
            engine = BacktestEngine(initial_balance=initial_balance, warmup_bars=min(80, len(candles) // 4))
            result = engine.run(candles, signal_fn)
            metric = self._metric_value(result.metrics) if result.metrics else 0
            self.results.append((params, metric))
            if metric > best_metric and result.metrics and result.metrics.total_trades >= 5:
                best_metric = metric
                best_params = params
        self.results.sort(key=lambda x: x[1], reverse=True)
        return OptimizationResult(
            best_params=best_params, best_metric=round(best_metric, 3),
            all_results=self.results[:20], metric_name=self.objective,
            iterations=iterations,
        )

    def top_n(self, n: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        return self.results[:n]
