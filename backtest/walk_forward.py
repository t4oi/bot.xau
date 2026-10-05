"""Walk-forward analysis — splits data into in-sample/out-of-sample windows."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List

from ..core.logging_config import get_logger
from ..data.base import Candle
from .engine import BacktestEngine, BacktestResult, SignalFn

logger = get_logger("backtest.walkforward")


@dataclass
class WalkForwardWindow:
    window_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    result: BacktestResult = field(default_factory=BacktestResult)


class WalkForwardAnalyzer:
    """Rolling walk-forward validation to test strategy robustness."""

    def __init__(self,
                 train_ratio: float = 0.7,
                 num_windows: int = 5,
                 initial_balance: float = 1000.0,
                 risk_per_trade_pct: float = 1.0):
        self.train_ratio = train_ratio
        self.num_windows = num_windows
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct

    def run(self, candles: List[Candle], signal_fn_factory: Callable[[List[Candle]], SignalFn]) -> List[WalkForwardWindow]:
        """Run walk-forward. signal_fn_factory(train_candles) returns a SignalFn tuned on train."""
        windows: List[WalkForwardWindow] = []
        n = len(candles)
        step = max(1, int(n / (self.num_windows + 1)))
        window_size = step * 2

        for w in range(self.num_windows):
            test_end = min(n, window_size + w * step)
            test_start = max(0, test_end - step)
            train_end = test_start
            train_start = max(0, train_end - int(step * self.train_ratio / (1 - self.train_ratio)))
            if test_end - test_start < 50:
                continue

            train_candles = candles[train_start:train_end]
            test_candles = candles[test_start:test_end]
            signal_fn = signal_fn_factory(train_candles)

            engine = BacktestEngine(
                initial_balance=self.initial_balance,
                risk_per_trade_pct=self.risk_per_trade_pct,
                warmup_bars=min(50, len(test_candles) // 4),
            )
            result = engine.run(test_candles, signal_fn)
            windows.append(WalkForwardWindow(
                window_index=w,
                train_start=train_start, train_end=train_end,
                test_start=test_start, test_end=test_end,
                result=result,
            ))
            logger.info("WF window %d: %d trades, PnL $%.2f",
                        w, result.metrics.total_trades, result.metrics.total_pnl_usd)

        return windows

    def aggregate(self, windows: List[WalkForwardWindow]) -> dict:
        if not windows:
            return {}
        total_trades = sum(w.result.metrics.total_trades for w in windows)
        total_pnl = sum(w.result.metrics.total_pnl_usd for w in windows)
        avg_wr = sum(w.result.metrics.win_rate_pct for w in windows) / len(windows)
        profitable = sum(1 for w in windows if w.result.metrics.total_pnl_usd > 0)
        return {
            "windows": len(windows),
            "profitable_windows": profitable,
            "robustness_pct": round(profitable / len(windows) * 100, 1),
            "total_trades": total_trades,
            "total_pnl_usd": round(total_pnl, 2),
            "avg_win_rate_pct": round(avg_wr, 1),
        }
