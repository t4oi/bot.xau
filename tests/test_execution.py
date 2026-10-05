"""Tests for execution module."""
import pytest
from xauusd_pro_bot.execution.order_manager import OrderManager, OrderSide, OrderType, OrderStatus
from xauusd_pro_bot.execution.position_tracker import PositionTracker
from xauusd_pro_bot.execution.slippage import SlippageModel


def test_order_creation_and_fill():
    om = OrderManager()
    order = om.create_order("XAUUSD", OrderSide.BUY, 0.1, OrderType.MARKET, price=2000.0)
    assert order.status == OrderStatus.PENDING
    filled = om.fill_order(order.id, 2000.5)
    assert filled.status == OrderStatus.FILLED
    assert filled.avg_fill_price == 2000.5


def test_order_cancel():
    om = OrderManager()
    order = om.create_order("XAUUSD", OrderSide.SELL, 0.1, OrderType.LIMIT, price=2050.0)
    cancelled = om.cancel_order(order.id)
    assert cancelled.status == OrderStatus.CANCELLED


def test_position_tracker():
    pt = PositionTracker()
    pos = pt.open_position("p1", "XAUUSD", OrderSide.BUY, 0.1, 2000.0,
                           stop_loss=1990.0, take_profit=2020.0)
    assert pos.quantity == 0.1
    pnl = pos.unrealized_pnl(2010.0)
    assert pnl > 0
    closed = pt.close_position("p1", 2015.0, "manual")
    assert closed["pnl_usd"] > 0
    assert len(pt.open_positions()) == 0


def test_slippage_model():
    sm = SlippageModel(seed=42)
    cost = sm.total_cost(2000.0, "BUY", 0.1, volatility=2.0)
    assert cost["fill_price"] > 2000.0
    assert cost["total_cost_usd"] >= 0
