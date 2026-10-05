"""Unit tests for indicators."""
import math
import pytest
from xauusd_pro_bot.indicators.trend import sma, ema, adx
from xauusd_pro_bot.indicators.momentum import rsi, macd
from xauusd_pro_bot.indicators.volatility import bollinger_bands, average_true_range


def test_sma_basic():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = sma(values, 3)
    assert math.isnan(result[0])
    assert math.isnan(result[1])
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)
    assert result[4] == pytest.approx(4.0)


def test_ema_length():
    values = list(range(1, 50))
    result = ema(values, 10)
    assert len(result) == len(values)
    assert not math.isnan(result[-1])


def test_rsi_range():
    values = [10 + (i % 5) * 0.5 for i in range(100)]
    result = rsi(values, 14)
    assert len(result) == 100
    last = result[-1]
    assert 0 <= last <= 100


def test_macd_returns_three():
    values = [100 + i * 0.1 + (i % 7) for i in range(100)]
    macd_line, signal_line, hist = macd(values)
    assert len(macd_line) == len(signal_line) == len(hist) == 100


def test_bollinger_bands():
    values = [100 + (i % 10) for i in range(50)]
    mid, upper, lower, pctb = bollinger_bands(values, 20, 2.0)
    assert len(mid) == 50
    assert upper[-1] >= mid[-1] >= lower[-1]


def test_atr_positive():
    highs = [10 + i * 0.1 for i in range(30)]
    lows = [9 + i * 0.1 for i in range(30)]
    closes = [9.5 + i * 0.1 for i in range(30)]
    atr = average_true_range(highs, lows, closes, 14)
    assert atr[-1] > 0


def test_adx():
    highs = [10 + i * 0.2 for i in range(50)]
    lows = [9 + i * 0.2 for i in range(50)]
    closes = [9.5 + i * 0.2 for i in range(50)]
    adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)
    assert len(adx_vals) == 50
