"""Unit tests for signal generation."""
import pytest
from xauusd_pro_bot.signal.tp_sl_calculator import TpSlCalculator
from xauusd_pro_bot.signal.filters import SignalFilter
from xauusd_pro_bot.signal.confluence_scorer import ConfluenceScorer
from xauusd_pro_bot.config.constants import SignalDirection
from xauusd_pro_bot.data.base import Candle
from xauusd_pro_bot.strategies.base import SignalVote


def _make_candles(n=100, trend=0.1):
    return [Candle(time=str(i), open=100+i*trend, high=101+i*trend,
                   low=99+i*trend, close=100.5+i*trend, volume=1000) for i in range(n)]


def test_tp_sl_calculator_buy():
    calc = TpSlCalculator()
    candles = _make_candles(100, 0.2)
    result = calc.compute(candles, SignalDirection.BUY, 2000.0, num_tps=3)
    assert result["entry"] == 2000.0
    assert result["stop_loss"] < 2000.0
    assert len(result["take_profits"]) == 3
    assert result["take_profits"][0] > 2000.0
    assert result["risk_reward_tp1"] > 0


def test_tp_sl_calculator_sell():
    calc = TpSlCalculator()
    candles = _make_candles(100, -0.2)
    result = calc.compute(candles, SignalDirection.SELL, 2000.0, num_tps=3)
    assert result["stop_loss"] > 2000.0
    assert result["take_profits"][0] < 2000.0


def test_signal_filter_spread():
    f = SignalFilter(max_spread=0.3)
    ok, reason = f.check_spread(0.5)
    assert not ok


def test_signal_filter_confluence():
    f = SignalFilter(min_confluence=70)
    ok, reason = f.check_confluence(50)
    assert not ok


def test_confluence_scorer():
    scorer = ConfluenceScorer()
    votes = [
        SignalVote(strategy="s1", direction=SignalDirection.BUY, confidence=60, timeframe="15m"),
        SignalVote(strategy="s2", direction=SignalDirection.BUY, confidence=50, timeframe="1h"),
        SignalVote(strategy="s3", direction=SignalDirection.SELL, confidence=30, timeframe="5m"),
    ]
    result = scorer.score(votes)
    assert result["direction"] == SignalDirection.BUY
    assert result["score_pct"] > 0
