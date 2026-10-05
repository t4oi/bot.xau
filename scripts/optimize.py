#!/usr/bin/env python3
"""Parameter optimization script — grid search over strategy parameters."""
import sys
sys.path.insert(0, ".")
from data.feed import FeedManager
from backtest.optimizer import ParameterOptimizer
from config.constants import SignalDirection


def signal_fn_factory(params):
    def signal_fn(cs):
        from strategies.trend_following import TrendFollowingStrategy
        strat = TrendFollowingStrategy(params=params)
        res = strat.analyze(cs, "1h")
        if res.net_direction == SignalDirection.NEUTRAL:
            return None
        entry = cs[-1].close
        risk = entry * params.get("risk_pct", 0.005)
        sl = entry - risk if res.net_direction == SignalDirection.BUY else entry + risk
        tp_mult = params.get("tp_mult", 2.0)
        tp = entry + tp_mult * risk if res.net_direction == SignalDirection.BUY else entry - tp_mult * risk
        return (res.net_direction, entry, sl, tp)
    return signal_fn


def main():
    feed = FeedManager()
    candles = feed.candles("1h", limit=1000)
    if not candles:
        print("No candles")
        sys.exit(1)

    grid = {
        "risk_pct": [0.003, 0.005, 0.008, 0.01],
        "tp_mult": [1.5, 2.0, 3.0, 4.0],
    }
    opt = ParameterOptimizer(param_grid=grid, objective="profit_factor")
    result = opt.grid_search(candles, signal_fn_factory, initial_balance=1000, max_evals=16)
    print(f"\nBest params: {result.best_params}")
    print(f"Best {result.metric_name}: {result.best_metric}")
    print("\nTop 5 combinations:")
    for params, metric in result.top_n(5):
        print(f"  {params} -> {metric:.3f}")


if __name__ == "__main__":
    main()
