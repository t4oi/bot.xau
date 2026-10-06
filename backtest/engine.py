"""Event-driven backtest engine — simulates TP/SL execution on historical bars."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from config.constants import SignalDirection
from core.logging_config import get_logger
from data.base import Candle
from .equity_curve import EquityCurve
from .metrics import PerformanceMetrics, compute_metrics

logger = get_logger("backtest.engine")


@dataclass
class BacktestTrade:
    id: int
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_bar: int
    exit_bar: int = -1
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_usd: float = 0.0
    duration_bars: int = 0
    lot_size: float = 0.01


@dataclass
class BacktestResult:
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: Optional[EquityCurve] = None
    metrics: Optional[PerformanceMetrics] = None
    bars_processed: int = 0
    signals_generated: int = 0


# Signal generator signature: (candles_so_far) -> Optional[(direction, entry, sl, tp)]
SignalFn = Callable[[List[Candle]], Optional[tuple]]


class BacktestEngine:
    """Walks through candles bar by bar, generating and executing signals."""

    def __init__(self,
                 initial_balance: float = 1000.0,
                 risk_per_trade_pct: float = 1.0,
                 spread: float = 0.20,
                 commission_per_lot: float = 0.0,
                 warmup_bars: int = 100):
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.spread = spread
        self.commission_per_lot = commission_per_lot
        self.warmup_bars = warmup_bars

    def run(self, candles: List[Candle], signal_fn: SignalFn) -> BacktestResult:
        result = BacktestResult()
        equity = self.initial_balance
        curve = EquityCurve(initial_balance=equity)
        open_trade: Optional[BacktestTrade] = None
        trade_id = 0

        for i in range(self.warmup_bars, len(candles)):
            bar = candles[i]
            result.bars_processed = i

            # Manage open trade
            if open_trade:
                hit_tp = hit_sl = False
                if open_trade.direction == SignalDirection.BUY:
                    if bar.low <= open_trade.stop_loss:
                        hit_sl = True
                    elif bar.high >= open_trade.take_profit:
                        hit_tp = True
                else:
                    if bar.high >= open_trade.stop_loss:
                        hit_sl = True
                    elif bar.low <= open_trade.take_profit:
                        hit_tp = True

                if hit_tp or hit_sl:
                    open_trade.exit_bar = i
                    open_trade.exit_price = open_trade.take_profit if hit_tp else open_trade.stop_loss
                    open_trade.exit_reason = "TP" if hit_tp else "SL"
                    open_trade.duration_bars = i - open_trade.entry_bar
                    # PnL: 1 lot = 100 oz => $100 per $1 move
                    pnl_per_lot = (open_trade.exit_price - open_trade.entry_price) * 100.0
                    if open_trade.direction == SignalDirection.SELL:
                        pnl_per_lot = -pnl_per_lot
                    open_trade.pnl_usd = round(pnl_per_lot * open_trade.lot_size - self.commission_per_lot * open_trade.lot_size, 2)
                    equity += open_trade.pnl_usd
                    result.trades.append(open_trade)
                    open_trade = None

            # Generate new signal if flat
            if open_trade is None:
                try:
                    sig = signal_fn(candles[:i + 1])
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Signal fn error at bar %d: %s", i, exc)
                    sig = None
                if sig:
                    result.signals_generated += 1
                    direction, entry, sl, tp = sig
                    risk_per_unit = abs(entry - sl)
                    risk_amount = equity * (self.risk_per_trade_pct / 100.0)
                    lot = risk_amount / (risk_per_unit * 100.0) if risk_per_unit > 0 else 0.01
                    lot = max(0.01, round(lot, 2))
                    trade_id += 1
                    open_trade = BacktestTrade(
                        id=trade_id, direction=direction,
                        entry_price=entry + (self.spread / 2 if direction == SignalDirection.BUY else -self.spread / 2),
                        stop_loss=sl, take_profit=tp,
                        entry_bar=i, lot_size=lot,
                    )

            curve.add(i, equity)

        # Close any open trade at last bar
        if open_trade and candles:
            last = candles[-1].close
            open_trade.exit_bar = len(candles) - 1
            open_trade.exit_price = last
            open_trade.exit_reason = "EOD"
            open_trade.duration_bars = open_trade.exit_bar - open_trade.entry_bar
            pnl_per_lot = (open_trade.exit_price - open_trade.entry_price) * 100.0
            if open_trade.direction == SignalDirection.SELL:
                pnl_per_lot = -pnl_per_lot
            open_trade.pnl_usd = round(pnl_per_lot * open_trade.lot_size, 2)
            equity += open_trade.pnl_usd
            result.trades.append(open_trade)
            curve.add(len(candles) - 1, equity)

        result.equity_curve = curve
        result.metrics = compute_metrics(result.trades, self.initial_balance)
        logger.info("Backtest complete: %d trades, PnL $%.2f, WR %.1f%%",
                    result.metrics.total_trades, result.metrics.total_pnl_usd,
                    result.metrics.win_rate_pct)
        return result
