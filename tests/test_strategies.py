"""Unit tests for strategies."""
import pytest
from xauusd_pro_bot.data.base import Candle
from xauusd_pro_bot.strategies.trend_following import TrendFollowingStrategy
from xauusd_pro_bot.strategies.mean_reversion import MeanReversionStrategy
from xauusd_pro_bot.strategies.breakout import BreakoutStrategy
from xauusd_pro_bot.strategies.registry import StrategyRegistry, register_defaults


def _make_candles(n=100, trend=0.1):
    return [Candle(time=str(i), open=100+i*trend, high=101+i*trend,
                   low=99+i*trend, close=100.5+i*trend, volume=1000) for i in range(n)]


def test_registry_registers_all():
    reg = StrategyRegistry()
    register_defaults(reg)
    assert len(reg) >= 8
    assert "trend_following" in reg
    assert "mean_reversion" in reg


def test_trend_following_returns_result():
    strat = TrendFollowingStrategy()
    candles = _make_candles(100, 0.3)
    result = strat.analyze(candles, "15m")
    assert result.strategy == "trend_following"
    assert len(result.votes) >= 1


def test_mean_reversion_returns_result():
    strat = MeanReversionStrategy()
    candles = _make_candles(100, 0.0)
    result = strat.analyze(candles, "15m")
    assert len(result.votes) >= 1


def test_breakout_returns_result():
    strat = BreakoutStrategy()
    candles = _make_candles(100, 0.2)
    result = strat.analyze(candles, "1h")
    assert len(result.votes) >= 1
