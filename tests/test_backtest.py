"""Tests for backtest engine."""
import pytest
from xauusd_pro_bot.data.base import Candle
from xauusd_pro_bot.backtest.engine import BacktestEngine
from xauusd_pro_bot.backtest.metrics import compute_metrics
from xauusd_pro_bot.backtest.monte_carlo import MonteCarloSimulator
from xauusd_pro_bot.config.constants import SignalDirection


def _uptrend_candles(n=200):
    return [Candle(time=str(i), open=100+i*0.2, high=101+i*0.2, low=99+i*0.2,
                   close=100.5+i*0.2, volume=1000) for i in range(n)]


def test_backtest_runs():
    candles = _uptrend_candles(200)

    def signal_fn(cs):
        if len(cs) < 50:
            return None
        if cs[-1].close > cs[-10].close:
            entry = cs[-1].close
            return (SignalDirection.BUY, entry, entry - 2, entry + 4)
        return None

    engine = BacktestEngine(initial_balance=1000, warmup_bars=50)
    result = engine.run(candles, signal_fn)
    assert result.bars_processed > 0
    assert result.metrics is not None
    assert result.equity_curve is not None


def test_compute_metrics_empty():
    m = compute_metrics([], 1000)
    assert m.total_trades == 0
    assert m.total_pnl_usd == 0


def test_monte_carlo():
    from xauusd_pro_bot.backtest.engine import BacktestTrade
    trades = [BacktestTrade(id=i, direction=SignalDirection.BUY, entry_price=2000,
                            stop_loss=1990, take_profit=2020, entry_bar=i,
                            pnl_usd=10 if i % 2 == 0 else -5) for i in range(20)]
    mc = MonteCarloSimulator(simulations=100, initial_balance=1000)
    result = mc.run(trades)
    assert result.simulations == 100
    assert result.median_final_equity > 0
