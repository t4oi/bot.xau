"""Unit tests for risk management."""
import pytest
from xauusd_pro_bot.risk.position_sizer import PositionSizer
from xauusd_pro_bot.risk.limits import RiskLimits
from xauusd_pro_bot.risk.drawdown_guard import DrawdownGuard


def test_position_sizer():
    sizer = PositionSizer(account_balance_usd=1000, risk_per_trade_pct=1.0)
    result = sizer.calculate(entry=2000.0, stop_loss=1990.0)
    assert result.lot_size > 0
    assert result.risk_amount_usd == pytest.approx(10.0, abs=0.01)
    assert result.risk_per_unit == pytest.approx(10.0)


def test_position_sizer_min_lot():
    sizer = PositionSizer(account_balance_usd=100, risk_per_trade_pct=0.1)
    result = sizer.calculate(entry=2000.0, stop_loss=1999.0)
    assert result.lot_size >= 0.01


def test_risk_limits_can_trade():
    limits = RiskLimits(max_daily_losses=3, account_balance=1000)
    allowed, reason = limits.can_trade()
    assert allowed


def test_risk_limits_halt_after_losses():
    limits = RiskLimits(max_daily_losses=2, account_balance=1000)
    limits.record_trade_result(-10)
    limits.record_trade_result(-10)
    allowed, reason = limits.can_trade()
    assert not allowed


def test_drawdown_guard():
    guard = DrawdownGuard(initial_balance=1000)
    guard.update(1100)
    guard.update(900)
    assert guard.current_drawdown_pct > 0
    assert guard.risk_multiplier <= 1.0
    assert guard.max_drawdown() > 0
