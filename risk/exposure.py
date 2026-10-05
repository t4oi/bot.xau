"""Exposure manager — tracks aggregate exposure and correlation risk."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from ..core.logging_config import get_logger

logger = get_logger("risk.exposure")


@dataclass
class ExposureLimit:
    max_total_lots: float = 5.0
    max_symbol_lots: float = 2.0
    max_simultaneous_trades: int = 5
    max_correlated_exposure: float = 3.0


class ExposureManager:
    """Tracks and limits total market exposure across positions."""

    def __init__(self, limits: ExposureLimit = None):
        self.limits = limits or ExposureLimit()
        self.positions: Dict[str, float] = {}  # symbol -> signed lot size
        self._closed_pnl: float = 0.0

    def can_open(self, symbol: str, lot_size: float, side: str) -> tuple:
        total = sum(abs(v) for v in self.positions.values())
        symbol_exposure = abs(self.positions.get(symbol, 0.0))
        trade_count = len([v for v in self.positions.values() if abs(v) > 0.001])

        if total + lot_size > self.limits.max_total_lots:
            return False, f"Total exposure {total:.2f} + {lot_size} > max {self.limits.max_total_lots}"
        if symbol_exposure + lot_size > self.limits.max_symbol_lots:
            return False, f"Symbol exposure {symbol_exposure:.2f} > max {self.limits.max_symbol_lots}"
        if trade_count >= self.limits.max_simultaneous_trades:
            return False, f"Max simultaneous trades {self.limits.max_simultaneous_trades} reached"
        return True, "OK"

    def open(self, symbol: str, lot_size: float, side: str) -> None:
        signed = lot_size if side.upper() == "BUY" else -lot_size
        self.positions[symbol] = self.positions.get(symbol, 0.0) + signed
        logger.info("Exposure updated: %s -> %.2f lots (total %.2f)",
                    symbol, self.positions[symbol], self.total_exposure)

    def close(self, symbol: str, lot_size: float, side: str) -> None:
        signed = lot_size if side.upper() == "BUY" else -lot_size
        self.positions[symbol] = self.positions.get(symbol, 0.0) - signed
        if abs(self.positions[symbol]) < 0.001:
            del self.positions[symbol]

    @property
    def total_exposure(self) -> float:
        return sum(abs(v) for v in self.positions.values())

    @property
    def net_direction(self) -> float:
        return sum(self.positions.values())

    def summary(self) -> dict:
        return {
            "positions": dict(self.positions),
            "total_exposure": round(self.total_exposure, 2),
            "net_direction": round(self.net_direction, 2),
            "trade_count": len(self.positions),
            "utilization_pct": round(self.total_exposure / self.limits.max_total_lots * 100, 1),
        }
