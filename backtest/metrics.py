"""Performance metrics for backtest evaluation."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List


@dataclass
class PerformanceMetrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate_pct: float = 0.0
    total_pnl_usd: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    recovery_factor: float = 0.0
    expectancy_usd: float = 0.0
    avg_rr: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    equity_final: float = 0.0
    equity_peak: float = 0.0
    avg_trade_duration_bars: float = 0.0


def compute_metrics(trades: List["BacktestTrade"], initial_balance: float = 1000.0) -> PerformanceMetrics:
    """Compute full performance metrics from a list of closed trades."""
    m = PerformanceMetrics()
    if not trades:
        return m

    m.total_trades = len(trades)
    pnls = [t.pnl_usd for t in trades]
    m.wins = sum(1 for p in pnls if p > 0)
    m.losses = sum(1 for p in pnls if p <= 0)
    m.win_rate_pct = round(m.wins / m.total_trades * 100.0, 2) if m.total_trades else 0.0

    m.total_pnl_usd = round(sum(pnls), 2)
    m.gross_profit = round(sum(p for p in pnls if p > 0), 2)
    m.gross_loss = round(abs(sum(p for p in pnls if p < 0)), 2)
    m.profit_factor = round(m.gross_profit / m.gross_loss, 2) if m.gross_loss > 0 else float("inf")

    win_vals = [p for p in pnls if p > 0]
    loss_vals = [abs(p) for p in pnls if p < 0]
    m.avg_win_usd = round(sum(win_vals) / len(win_vals), 2) if win_vals else 0.0
    m.avg_loss_usd = round(sum(loss_vals) / len(loss_vals), 2) if loss_vals else 0.0
    m.largest_win = round(max(win_vals), 2) if win_vals else 0.0
    m.largest_loss = round(min(pnls), 2) if pnls else 0.0
    m.expectancy_usd = round(m.total_pnl_usd / m.total_trades, 2) if m.total_trades else 0.0

    # Equity curve & drawdown
    equity = initial_balance
    peak = initial_balance
    max_dd_usd = 0.0
    equity_curve = [initial_balance]
    for p in pnls:
        equity += p
        equity_curve.append(equity)
        peak = max(peak, equity)
        dd = peak - equity
        max_dd_usd = max(max_dd_usd, dd)
    m.equity_final = round(equity, 2)
    m.equity_peak = round(peak, 2)
    m.max_drawdown_usd = round(max_dd_usd, 2)
    m.max_drawdown_pct = round(max_dd_usd / peak * 100.0, 2) if peak > 0 else 0.0

    # Sharpe (per-trade returns)
    returns = [p / initial_balance for p in pnls]
    mean_ret = sum(returns) / len(returns) if returns else 0
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns)) if returns else 0
    m.sharpe_ratio = round(mean_ret / std_ret * math.sqrt(m.total_trades), 2) if std_ret > 0 else 0.0

    downside = [r for r in returns if r < 0]
    downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 0
    m.sortino_ratio = round(mean_ret / downside_std * math.sqrt(m.total_trades), 2) if downside_std > 0 else 0.0

    m.calmar_ratio = round(m.total_pnl_usd / max_dd_usd, 2) if max_dd_usd > 0 else 0.0
    m.recovery_factor = round(m.total_pnl_usd / max_dd_usd, 2) if max_dd_usd > 0 else float("inf")

    # Consecutive streaks
    cur_w = cur_l = 0
    for p in pnls:
        if p > 0:
            cur_w += 1
            cur_l = 0
            m.consecutive_wins = max(m.consecutive_wins, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            m.consecutive_losses = max(m.consecutive_losses, cur_l)

    durations = [t.duration_bars for t in trades if t.duration_bars > 0]
    m.avg_trade_duration_bars = round(sum(durations) / len(durations), 1) if durations else 0.0

    return m
