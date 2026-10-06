"""Monte Carlo simulation — stress-test strategy robustness."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List

from core.logging_config import get_logger
from .engine import BacktestTrade, BacktestResult
from .metrics import compute_metrics, PerformanceMetrics

logger = get_logger("backtest.montecarlo")


@dataclass
class MonteCarloResult:
    simulations: int = 0
    median_final_equity: float = 0.0
    p5_final_equity: float = 0.0
    p95_final_equity: float = 0.0
    median_max_drawdown_pct: float = 0.0
    ruin_probability: float = 0.0
    profit_probability: float = 0.0
    equity_paths: List[List[float]] = field(default_factory=list)


class MonteCarloSimulator:
    """Reshuffles trade order to estimate distribution of outcomes."""

    def __init__(self, simulations: int = 1000, initial_balance: float = 1000.0,
                 ruin_level: float = 0.5, seed: int = 42):
        self.simulations = simulations
        self.initial_balance = initial_balance
        self.ruin_level = ruin_level
        self.rng = random.Random(seed)

    def run(self, trades: List[BacktestTrade]) -> MonteCarloResult:
        if not trades:
            return MonteCarloResult()
        pnls = [t.pnl_usd for t in trades]
        final_equities = []
        max_drawdowns = []
        equity_paths = []
        ruin_count = 0
        profit_count = 0

        for sim in range(self.simulations):
            shuffled = pnls[:]
            self.rng.shuffle(shuffled)
            equity = self.initial_balance
            peak = equity
            max_dd = 0.0
            path = [equity]
            for p in shuffled:
                equity += p
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100.0 if peak > 0 else 0
                max_dd = max(max_dd, dd)
                path.append(equity)
                if equity <= self.initial_balance * self.ruin_level:
                    ruin_count += 1
                    break
            final_equities.append(equity)
            max_drawdowns.append(max_dd)
            equity_paths.append(path[::max(1, len(path) // 50)])
            if equity > self.initial_balance:
                profit_count += 1

        final_equities.sort()
        max_drawdowns.sort()
        result = MonteCarloResult(
            simulations=self.simulations,
            median_final_equity=round(final_equities[len(final_equities) // 2], 2),
            p5_final_equity=round(final_equities[int(len(final_equities) * 0.05)], 2),
            p95_final_equity=round(final_equities[int(len(final_equities) * 0.95)], 2),
            median_max_drawdown_pct=round(max_drawdowns[len(max_drawdowns) // 2], 2),
            ruin_probability=round(ruin_count / self.simulations * 100, 2),
            profit_probability=round(profit_count / self.simulations * 100, 2),
            equity_paths=equity_paths[:20],  # keep subset for plotting
        )
        logger.info("Monte Carlo: ruin prob %.1f%%, profit prob %.1f%%, median equity $%.2f",
                    result.ruin_probability, result.profit_probability, result.median_final_equity)
        return result

    def summary_text(self, result: MonteCarloResult) -> str:
        return (
            f"Monte Carlo Simulation ({result.simulations} runs):\n"
            f"  Median final equity : ${result.median_final_equity:.2f}\n"
            f"  5th percentile (worst case): ${result.p5_final_equity:.2f}\n"
            f"  95th percentile (best case): ${result.p95_final_equity:.2f}\n"
            f"  Median max drawdown : {result.median_max_drawdown_pct:.1f}%\n"
            f"  Ruin probability    : {result.ruin_probability:.1f}%\n"
            f"  Profit probability  : {result.profit_probability:.1f}%\n"
        )
