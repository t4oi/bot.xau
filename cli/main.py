"""CLI main — rich command-line interface with subcommands."""
from __future__ import annotations
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_health(args):
    """Check health of all components."""
    from scripts.health_check import main as health_main
    return health_main()


def cmd_scan_once(args):
    """Run a single scan cycle and print result."""
    from config.settings import get_settings
    from data.feed import FeedManager
    from strategies.multi_tf_confluence import MultiTimeframeConfluence
    from signal.generator import SignalGenerator
    from signal.filters import SignalFilter
    from signal.tp_sl_calculator import TpSlCalculator
    from risk.limits import RiskLimits
    from risk.position_sizer import PositionSizer

    settings = get_settings()
    feed = FeedManager()
    mtf = MultiTimeframeConfluence(timeframes=settings.timeframe_list)
    candles_by_tf = feed.multi_timeframe(settings.timeframe_list, limit=500)
    votes_by_tf = mtf.scan(candles_by_tf)
    all_votes = [v for votes in votes_by_tf.values() for v in votes]
    print(f"Collected {len(all_votes)} strategy votes")
    for tf, votes in votes_by_tf.items():
        net = sum(v.signed_score for v in votes)
        print(f"  {tf}: net score = {net:.1f} ({len(votes)} votes)")

    generator = SignalGenerator(
        calculator=TpSlCalculator(),
        signal_filter=SignalFilter(min_confluence=settings.min_confluence_score),
    )
    primary = candles_by_tf.get(settings.primary_timeframe, [])
    tick = feed.tick()
    signal = generator.generate(all_votes, primary, tick=tick,
                                primary_tf=settings.primary_timeframe,
                                symbol=settings.trading_symbol)
    if signal:
        print(f"\nSIGNAL: {signal.direction.value} @ {signal.entry}")
        print(f"  SL: {signal.stop_loss}, TPs: {signal.take_profits}")
        print(f"  Confluence: {signal.confluence_pct}%, R:R 1:{signal.risk_reward}")
        sizer = PositionSizer(settings.account_balance_usd, settings.risk_per_trade_pct)
        size = sizer.calculate(signal.entry, signal.stop_loss)
        print(f"  Suggested lot: {size.lot_size} (risk ${size.risk_amount_usd})")
    else:
        print("\nNo signal generated (filtered or neutral).")
    return 0


def cmd_backtest(args):
    """Run backtest with specified parameters."""
    from data.feed import FeedManager
    from config.settings import get_settings
    from backtest.engine import BacktestEngine
    from backtest.report import BacktestReport
    from backtest.monte_carlo import MonteCarloSimulator

    settings = get_settings()
    feed = FeedManager()
    candles = feed.candles(args.timeframe or settings.primary_timeframe, limit=args.limit)
    if not candles:
        print("No candles available for backtest")
        return 1

    def signal_fn(cs):
        from strategies.trend_following import TrendFollowingStrategy
        from config.constants import SignalDirection
        strat = TrendFollowingStrategy()
        res = strat.analyze(cs, args.timeframe or settings.primary_timeframe)
        if res.net_direction == SignalDirection.NEUTRAL:
            return None
        entry = cs[-1].close
        risk = entry * 0.005
        sl = entry - risk if res.net_direction == SignalDirection.BUY else entry + risk
        tp = entry + 2 * risk if res.net_direction == SignalDirection.BUY else entry - 2 * risk
        return (res.net_direction, entry, sl, tp)

    engine = BacktestEngine(initial_balance=settings.account_balance_usd,
                            risk_per_trade_pct=settings.risk_per_trade_pct)
    result = engine.run(candles, signal_fn)
    print(BacktestReport.text_report(result))

    if args.montecarlo and result.trades:
        mc = MonteCarloSimulator(simulations=args.mc_sims,
                                 initial_balance=settings.account_balance_usd)
        mc_result = mc.run(result.trades)
        print(mc.summary_text(mc_result))
    return 0


def cmd_optimize(args):
    """Run parameter optimization."""
    print("Optimization — use scripts/optimize.py for full grid search.")
    return 0


def cmd_export(args):
    """Export signals/trades to CSV."""
    from database.repository import Repository
    from config.settings import get_settings
    repo = Repository(get_settings().database_url)
    signals = repo.recent_signals(args.limit)
    import csv as csv_mod
    out_path = args.output or "signals_export.csv"
    with open(out_path, "w", newline="") as f:
        w = csv_mod.writer(f)
        w.writerow(["id", "symbol", "direction", "entry", "stop_loss", "take_profits",
                    "confluence", "timeframe", "created_at", "outcome"])
        for s in signals:
            w.writerow([s.signal_id, s.symbol, s.direction, s.entry, s.stop_loss,
                        s.take_profits, s.confluence_pct, s.timeframe, s.created_at, s.outcome])
    print(f"Exported {len(signals)} signals to {out_path}")
    return 0


def cmd_status(args):
    """Print bot status summary."""
    from database.repository import Repository
    from config.settings import get_settings
    from data.feed import FeedManager
    repo = Repository(get_settings().database_url)
    feed = FeedManager()
    health = feed.health()
    stats = repo.daily_stats()
    print(f"Data source: {health['source']} (healthy={health['healthy']})")
    tick = feed.tick()
    if tick:
        print(f"XAUUSD price: {tick.mid:.2f} (spread {tick.spread:.2f})")
    print(f"Today: {stats['signals_sent']} signals, {stats['wins']}W/{stats['losses']}L, "
          f"PnL ${stats['pnl']:.2f}, WR {stats['win_rate']:.1f}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="XAUUSD Pro Bot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Health check")
    sub.add_parser("scan", help="Single scan cycle")
    bt = sub.add_parser("backtest", help="Run backtest")
    bt.add_argument("--timeframe", default=None)
    bt.add_argument("--limit", type=int, default=1000)
    bt.add_argument("--montecarlo", action="store_true")
    bt.add_argument("--mc-sims", type=int, default=500)
    sub.add_parser("optimize", help="Parameter optimization")
    exp = sub.add_parser("export", help="Export signals to CSV")
    exp.add_argument("--output", default=None)
    exp.add_argument("--limit", type=int, default=100)
    sub.add_parser("status", help="Status summary")
    return parser


def cli_main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "health": cmd_health, "scan": cmd_scan_once, "backtest": cmd_backtest,
        "optimize": cmd_optimize, "export": cmd_export, "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(cli_main())
