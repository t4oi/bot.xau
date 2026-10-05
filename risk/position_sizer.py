"""Position sizing — lot size based on account balance, risk % and SL distance."""
from __future__ import annotations
from dataclasses import dataclass

from ..config.constants import SYMBOL_CONTRACT_SIZE, SYMBOL_PIP_VALUE_PER_LOT_USD


@dataclass
class PositionSizeResult:
    lot_size: float
    risk_amount_usd: float
    units: float
    risk_per_unit: float
    max_lot_exceeded: bool = False


class PositionSizer:
    """Calculate appropriate lot size for a trade."""

    def __init__(self,
                 account_balance_usd: float = 1000.0,
                 risk_per_trade_pct: float = 1.0,
                 max_lot: float = 10.0,
                 min_lot: float = 0.01):
        self.account_balance_usd = account_balance_usd
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_lot = max_lot
        self.min_lot = min_lot

    def calculate(self, entry: float, stop_loss: float) -> PositionSizeResult:
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit <= 0:
            return PositionSizeResult(0.0, 0.0, 0.0, 0.0)

        risk_amount = self.account_balance_usd * (self.risk_per_trade_pct / 100.0)

        # For XAUUSD: 1 lot = 100 oz, $1 per 0.01 move per lot
        # PnL per lot = (price_diff / 0.01) * $1 = price_diff * 100
        pnl_per_lot_per_unit = SYMBOL_CONTRACT_SIZE  # 100 USD per $1 move per lot
        lot_size = risk_amount / (risk_per_unit * pnl_per_lot_per_unit)

        max_exceeded = False
        if lot_size > self.max_lot:
            lot_size = self.max_lot
            max_exceeded = True
        if lot_size < self.min_lot:
            lot_size = self.min_lot

        # Round to 2 decimal places (broker standard)
        lot_size = round(lot_size, 2)
        units = lot_size * SYMBOL_CONTRACT_SIZE

        return PositionSizeResult(
            lot_size=lot_size,
            risk_amount_usd=round(risk_amount, 2),
            units=round(units, 2),
            risk_per_unit=round(risk_per_unit, 2),
            max_lot_exceeded=max_exceeded,
        )

    def update_balance(self, pnl_usd: float) -> None:
        self.account_balance_usd += pnl_usd
