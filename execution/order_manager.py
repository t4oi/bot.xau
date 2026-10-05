"""Order manager — simulates and tracks orders with full lifecycle states."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from ..core.logging_config import get_logger

logger = get_logger("execution.orders")


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    filled_at: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY


class OrderManager:
    """Manages the full order book lifecycle."""

    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._history: List[Order] = []

    def create_order(self, symbol: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     price: float = 0.0, stop_loss: float = 0.0,
                     take_profit: float = 0.0, metadata: Optional[Dict] = None) -> Order:
        order = Order(
            id=str(uuid.uuid4())[:12], symbol=symbol, side=side,
            order_type=order_type, quantity=quantity, price=price,
            stop_loss=stop_loss, take_profit=take_profit,
            metadata=metadata or {},
        )
        self._orders[order.id] = order
        logger.info("Order created: %s %s %s @ %s", order.id, side.value, quantity, price or "MARKET")
        return order

    def fill_order(self, order_id: str, fill_price: float, quantity: Optional[float] = None) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise KeyError(f"Order {order_id} not found")
        qty = quantity or order.quantity
        order.filled_quantity += qty
        total_cost = order.avg_fill_price * (order.filled_quantity - qty) + fill_price * qty
        order.avg_fill_price = total_cost / order.filled_quantity if order.filled_quantity > 0 else 0
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow().isoformat()
            self._history.append(order)
            del self._orders[order_id]
        else:
            order.status = OrderStatus.PARTIALLY_FILLED
        logger.info("Order %s filled: %.2f @ %.2f", order_id, qty, fill_price)
        return order

    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = self._orders.pop(order_id, None)
        if order:
            order.status = OrderStatus.CANCELLED
            self._history.append(order)
            logger.info("Order %s cancelled", order_id)
        return order

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        orders = list(self._orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_order_history(self, limit: int = 100) -> List[Order]:
        return self._history[-limit:]

    def pending_limit_orders(self) -> List[Order]:
        return [o for o in self._orders.values() if o.order_type != OrderType.MARKET]

    def check_triggers(self, current_price: float) -> List[Order]:
        """Check pending stop/limit orders and return those that should trigger."""
        triggered = []
        for order in list(self._orders.values()):
            if order.order_type == OrderType.LIMIT:
                if order.is_buy and current_price <= order.price:
                    triggered.append(order)
                elif not order.is_buy and current_price >= order.price:
                    triggered.append(order)
            elif order.order_type == OrderType.STOP:
                if order.is_buy and current_price >= order.price:
                    triggered.append(order)
                elif not order.is_buy and current_price <= order.price:
                    triggered.append(order)
        return triggered

    def stats(self) -> dict:
        return {
            "open_orders": len(self._orders),
            "total_orders": len(self._history) + len(self._orders),
            "filled": sum(1 for o in self._history if o.status == OrderStatus.FILLED),
            "cancelled": sum(1 for o in self._history if o.status == OrderStatus.CANCELLED),
        }
