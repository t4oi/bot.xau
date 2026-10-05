"""Backtest report generator — text + HTML summary."""
from __future__ import annotations
from typing import List

from ..core.utils import format_usd
from .engine import BacktestResult
from .walk_forward import WalkForwardWindow


class BacktestReport:
    """Formats backtest results into readable reports."""

    @staticmethod
    def text_report(result: BacktestResult) -> str:
        m = result.metrics
        if not m:
            return "No metrics available."
        lines = [
            "=" * 55,
            "         BACKTEST REPORT — XAUUSD PRO BOT",
            "=" * 55,
            f"Bars processed     : {result.bars_processed}",
            f"Signals generated  : {result.signals_generated}",
            f"Total trades       : {m.total_trades}",
            f"Wins / Losses      : {m.wins} / {m.losses}",
            f"Win rate           : {m.win_rate_pct}%",
            f"Total PnL          : {format_usd(m.total_pnl_usd)}",
            f"Gross profit       : {format_usd(m.gross_profit)}",
            f"Gross loss         : {format_usd(m.gross_loss)}",
            f"Profit factor      : {m.profit_factor}",
            f"Expectancy / trade : {format_usd(m.expectancy_usd)}",
            f"Avg win / Avg loss : {format_usd(m.avg_win_usd)} / {format_usd(m.avg_loss_usd)}",
            f"Largest win / loss : {format_usd(m.largest_win)} / {format_usd(m.largest_loss)}",
            f"Max drawdown       : {m.max_drawdown_pct}% ({format_usd(m.max_drawdown_usd)})",
            f"Sharpe ratio       : {m.sharpe_ratio}",
            f"Sortino ratio      : {m.sortino_ratio}",
            f"Calmar ratio       : {m.calmar_ratio}",
            f"Recovery factor    : {m.recovery_factor}",
            f"Max cons. wins     : {m.consecutive_wins}",
            f"Max cons. losses   : {m.consecutive_losses}",
            f"Final equity       : {format_usd(m.equity_final)}",
            "=" * 55,
        ]
        return "\n".join(lines)

    @staticmethod
    def walk_forward_summary(windows: List[WalkForwardWindow]) -> str:
        if not windows:
            return "No walk-forward windows."
        lines = ["Walk-Forward Analysis:", "-" * 40]
        for w in windows:
            m = w.result.metrics
            lines.append(
                f"Window {w.window_index}: trades={m.total_trades}, "
                f"WR={m.win_rate_pct}%, PnL={format_usd(m.total_pnl_usd)}, "
                f"PF={m.profit_factor}"
            )
        return "\n".join(lines)

    @staticmethod
    def html_report(result: BacktestResult) -> str:
        m = result.metrics
        if not m:
            return "<p>No metrics.</p>"
        rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in {
                "Total Trades": m.total_trades, "Win Rate": f"{m.win_rate_pct}%",
                "Total PnL": format_usd(m.total_pnl_usd),
                "Profit Factor": m.profit_factor, "Sharpe": m.sharpe_ratio,
                "Max Drawdown": f"{m.max_drawdown_pct}%",
                "Expectancy": format_usd(m.expectancy_usd),
            }.items()
        )
        return f"<table class='bt-table'><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table>"
