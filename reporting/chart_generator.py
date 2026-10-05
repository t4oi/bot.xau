"""Chart generator — ASCII + HTML charts for reports (no matplotlib dependency)."""
from __future__ import annotations
from typing import List, Tuple


class ASCIIChart:
    """Simple ASCII sparkline/bar charts for Telegram messages."""

    BARS = "▁▂▃▄▅▆▇█"

    @classmethod
    def sparkline(cls, values: List[float]) -> str:
        if not values:
            return ""
        lo, hi = min(values), max(values)
        rng = hi - lo or 1
        return "".join(cls.BARS[min(7, int((v - lo) / rng * 7))] for v in values)

    @classmethod
    def bar_chart(cls, data: List[Tuple[str, float]], width: int = 20) -> str:
        if not data:
            return ""
        max_val = max(abs(v) for _, v in data) or 1
        lines = []
        for label, value in data:
            bar_len = int(abs(value) / max_val * width)
            bar = "█" * bar_len
            sign = "+" if value >= 0 else "-"
            lines.append(f"{label:>8} |{bar:<{width}} {sign}${abs(value):.2f}")
        return "\n".join(lines)

    @classmethod
    def equity_curve_ascii(cls, equity: List[float], width: int = 40, height: int = 10) -> str:
        if not equity:
            return ""
        lo, hi = min(equity), max(equity)
        rng = hi - lo or 1
        grid = [[" "] * width for _ in range(height)]
        step = max(1, len(equity) // width)
        for col in range(width):
            idx = min(col * step, len(equity) - 1)
            row = height - 1 - int((equity[idx] - lo) / rng * (height - 1))
            grid[row][col] = "●"
        return "\n".join("".join(row) for row in grid) + f"\n  Low: ${lo:.0f}  High: ${hi:.0f}  Final: ${equity[-1]:.0f}"


class HTMLChart:
    """Generate simple HTML/SVG charts for the web dashboard."""

    @staticmethod
    def line_chart_svg(values: List[float], width: int = 600, height: int = 200,
                       color: str = "#fbbf24") -> str:
        if not values:
            return "<p>No data</p>"
        lo, hi = min(values), max(values)
        rng = hi - lo or 1
        points = []
        for i, v in enumerate(values):
            x = i / (len(values) - 1) * width if len(values) > 1 else 0
            y = height - (v - lo) / rng * (height - 20) - 10
            points.append(f"{x:.1f},{y:.1f}")
        polyline = " ".join(points)
        return (f'<svg viewBox="0 0 {width} {height}" class="chart">'
                f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"/>'
                f'</svg>')

    @staticmethod
    def equity_curve_html(equity: List[float]) -> str:
        return HTMLChart.line_chart_svg(equity, color="#22c55e" if equity[-1] >= equity[0] else "#ef4444")
