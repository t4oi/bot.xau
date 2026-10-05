"""Position tracker — tracks open positions with floating P&L."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.logging_config import get_logger
from .order_manager import OrderSide

logger = get_logger("execution.positions")


@dataclass
class Position:
    symbol: str
    side: OrderSide
    quantity: float
    avg_entry: float
    stop_loss: float = 0.0
    take_profit: float = 0.0
    breakeven_moved: bool = False
    opened_at: str = ""
    metadata: Dict = field(default_factory=dict)

    @property
    def is_long(self) -> bool:
        return self.side == OrderSide.BUY

    def unrealized_pnl(self, current_price: float) -> float:
        diff = current_price - self.avg_entry if self.is_long else self.avg_entry - current_price
        return diff * self.quantity * 100.0  # XAUUSD: 1 lot = 100 oz

    def pnl_pct(self, current_price: float) -> float:
        if self.avg_entry <= 0:
            return 0.0
        diff = current_price - self.avg_entry if self.is_long else self.avg_entry - current_price
        return diff / self.avg_entry * 100.0

    def distance_to_sl(self, current_price: float) -> float:
        if self.stop_loss <= 0:
            return float("inf")
        return abs(current_price - self.stop_loss)

    def distance_to_tp(self, current_price: float) -> float:
        if self.take_profit <= 0:
            return float("inf")
        return abs(self.take_profit - current_price)


class PositionTracker:
    """Tracks all open positions and their P&L."""

    def __init__(self):
        self._positions: Dict[str, Position] = {}  # keyed by position_id
        self._closed: List[Dict] = []

    def open_position(self, position_id: str, symbol: str, side: OrderSide,
                      quantity: float, entry_price: float,
                      stop_loss: float = 0.0, take_profit: float = 0.0) -> Position:
        pos = Position(
            symbol=symbol, side=side, quantity=quantity, avg_entry=entry_price,
            stop_loss=stop_loss, take_profit=take_profit,
            opened_at="", metadata={},
        )
        self._positions[position_id] = pos
        logger.info("Position opened: %s %s %.2f @ %.2f", position_id, side.value, quantity, entry_price)
        return pos

    def close_position(self, position_id: str, exit_price: float, reason: str = "") -> Optional[Dict]:
        pos = self._positions.pop(position_id, None)
        if not pos:
            return None
        pnl = pos.unrealized_pnl(exit_price)
        record = {
            "position_id": position_id, "symbol": pos.symbol, "side": pos.side.value,
            "quantity": pos.quantity, "entry": pos.avg_entry, "exit": exit_price,
            "pnl_usd": round(pnl, 2), "reason": reason,
        }
        self._closed.append(record)
        logger.info("Position %s closed @ %.2f PnL=$%.2f (%s)", position_id, exit_price, pnl, reason)
        return record

    def move_to_breakeven(self, position_id: str) -> bool:
        pos = self._positions.get(position_id)
        if not pos or pos.breakeven_moved:
            return False
        pos.stop_loss = pos.avg_entry
        pos.breakeven_moved = True
        logger.info("Position %s SL moved to breakeven", position_id)
        return True

    def partial_close(self, position_id: str, fraction: float, current_price: float) -> Optional[Dict]:
        pos = self._positions.get(position_id)
        if not pos or fraction <= 0 or fraction > 1:
            return None
        close_qty = pos.quantity * fraction
        pnl = (current_price - pos.avg_entry) * close_qty * 100.0 if pos.is_long else \
              (pos.avg_entry - current_price) * close_qty * 100.0
        pos.quantity -= close_qty
        record = {
            "position_id": position_id, "fraction": fraction, "close_qty": close_qty,
            "price": current_price, "pnl_usd": round(pnl, 2),
        }
        self._closed.append(record)
        if pos.quantity <= 0.001:
            self._positions.pop(position_id, None)
        return record

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def open_positions(self) -> List[Position]:
        return list(self._positions.values())

    def total_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        total = 0.0
        for pos in self._positions.values():
            price = prices.get(pos.symbol, pos.avg_entry)
            total += pos.unrealized_pnl(price)
        return round(total, 2)

    def check_exits(self, current_price: float) -> List[Dict]:
        """Check all positions for SL/TP hits. Returns closed records."""
        closed = []
        for pid, pos in list(self._positions.items()):
            if pos.is_long:
                if pos.stop_loss > 0 and current_price <= pos.stop_loss:
                    closed.append(self.close_position(pid, pos.stop_loss, "SL"))
                elif pos.take_profit > 0 and current_price >= pos.take_profit:
                    closed.append(self.close_position(pid, pos.take_profit, "TP"))
            else:
                if pos.stop_loss > 0 and current_price >= pos.stop_loss:
                    closed.append(self.close_position(pid, pos.stop_loss, "SL"))
                elif pos.take_profit > 0 and current_price <= pos.take_profit:
                    closed.append(self.close_position(pid, pos.take_profit, "TP"))
        return [c for c in closed if c]

    def closed_history(self) -> List[Dict]:
        return self._closed

    def summary(self, current_price: float) -> dict:
        opens = self.open_positions()
        return {
            "open_count": len(opens),
            "long_count": sum(1 for p in opens if p.is_long),
            "short_count": sum(1 for p in opens if not p.is_long),
            "total_exposure": sum(p.quantity for p in opens),
            "unrealized_pnl": self.total_unrealized_pnl({p.symbol: current_price for p in opens}),
            "closed_count": len(self._closed),
            "closed_pnl": round(sum(c.get("pnl_usd", 0) for c in self._closed), 2),
        }
