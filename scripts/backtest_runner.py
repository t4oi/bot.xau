#!/usr/bin/env python3
"""Backtest runner script — full backtest + Monte Carlo + Walk-Forward report."""
import sys
sys.path.insert(0, ".")
from config.settings import get_settings
from data.feed import FeedManager
from backtest.engine import BacktestEngine
from backtest.report import BacktestReport
from backtest.monte_carlo import MonteCarloSimulator
from backtest.walk_forward import WalkForwardAnalyzer
from config.constants import SignalDirection


def signal_factory(params):
    def signal_fn(cs):
        from strategies.trend_following import TrendFollowingStrategy
        strat = TrendFollowingStrategy(params=params)
        res = strat.analyze(cs, "1h")
        if res.net_direction == SignalDirection.NEUTRAL:
            return None
        entry = cs[-1].close
        risk = entry * params.get("risk_pct", 0.005)
        sl = entry - risk if res.net_direction == SignalDirection.BUY else entry + risk
        tp = entry + 2 * risk if res.net_direction == SignalDirection.BUY else entry - 2 * risk
        return (res.net_direction, entry, sl, tp)
    return signal_fn


def main():
    settings = get_settings()
    feed = FeedManager()
    candles = feed.candles("1h", limit=1000)
    if not candles:
        print("No candles — check data source")
        sys.exit(1)
    print(f"Loaded {len(candles)} candles")

    engine = BacktestEngine(initial_balance=settings.account_balance_usd)
    result = engine.run(candles, signal_factory({"risk_pct": 0.005}))
    print(BacktestReport.text_report(result))

    if result.trades:
        print("\n" + "=" * 55)
        mc = MonteCarloSimulator(simulations=1000, initial_balance=settings.account_balance_usd)
        mc_result = mc.run(result.trades)
        print(mc.summary_text(mc_result))

        print("\n" + "=" * 55)
        wf = WalkForwardAnalyzer(num_windows=5, initial_balance=settings.account_balance_usd)
        windows = wf.run(candles, lambda train: signal_factory({"risk_pct": 0.005}))
        print(BacktestReport.walk_forward_summary(windows))
        agg = wf.aggregate(windows)
        print(f"Robustness: {agg.get('robustness_pct', 0)}% windows profitable")


if __name__ == "__main__":
    main()
