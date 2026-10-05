"""Trade lifecycle manager — orchestrates entry -> management -> exit."""
from __future__ import annotations
from typing import Dict, List, Optional

from ..core.logging_config import get_logger
from ..signal.generator import TradingSignal
from .order_manager import OrderManager, OrderSide, OrderType
from .position_tracker import PositionTracker
from .slippage import SlippageModel

logger = get_logger("execution.lifecycle")


class TradeLifecycleManager:
    """Full trade lifecycle: signal -> order -> position -> management -> exit."""

    def __init__(self, slippage: Optional[SlippageModel] = None):
        self.orders = OrderManager()
        self.positions = PositionTracker()
        self.slippage = slippage or SlippageModel()
        self._signal_to_position: Dict[str, str] = {}

    def on_signal(self, signal: TradingSignal, current_price: float, lot_size: float) -> Optional[str]:
        """Execute a signal: create order, fill, open position."""
        side = OrderSide.BUY if signal.is_buy else OrderSide.SELL
        cost = self.slippage.total_cost(signal.entry, side.value, lot_size, signal.atr)
        fill_price = cost["fill_price"]

        order = self.orders.create_order(
            symbol=signal.symbol, side=side, quantity=lot_size,
            order_type=OrderType.MARKET, price=fill_price,
            stop_loss=signal.stop_loss, take_profit=signal.take_profits[0] if signal.take_profits else 0,
            metadata={"signal_id": signal.id, "confluence": signal.confluence_pct},
        )
        self.orders.fill_order(order.id, fill_price)

        position_id = f"pos_{signal.id}"
        self.positions.open_position(
            position_id=position_id, symbol=signal.symbol, side=side,
            quantity=lot_size, entry_price=fill_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profits[0] if signal.take_profits else 0,
        )
        self._signal_to_position[signal.id] = position_id
        logger.info("Signal %s -> position %s opened @ %.2f", signal.id, position_id, fill_price)
        return position_id

    def on_price_update(self, current_price: float) -> List[Dict]:
        """Process price tick: check exits, breakeven, partial closes."""
        # Check SL/TP
        closed = self.positions.check_exits(current_price)
        # Move to breakeven when in profit by 1R
        for pid, pos in list(self.positions._positions.items()):
            if not pos.breakeven_moved and pos.stop_loss > 0:
                risk = abs(pos.avg_entry - pos.stop_loss)
                if pos.is_long and current_price >= pos.avg_entry + risk:
                    self.positions.move_to_breakeven(pid)
                elif not pos.is_long and current_price <= pos.avg_entry - risk:
                    self.positions.move_to_breakeven(pid)
        return closed

    def close_all(self, current_price: float, reason: str = "manual") -> List[Dict]:
        closed = []
        for pid in list(self.positions._positions.keys()):
            rec = self.positions.close_position(pid, current_price, reason)
            if rec:
                closed.append(rec)
        return closed

    def status(self, current_price: float) -> dict:
        return {
            "orders": self.orders.stats(),
            "positions": self.positions.summary(current_price),
        }
