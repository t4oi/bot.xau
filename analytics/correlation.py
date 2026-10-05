"""Correlation analyzer — multi-asset correlation & lead-lag detection."""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple


class CorrelationAnalyzer:
    """Computes rolling correlations between price series."""

    @staticmethod
    def pearson(x: List[float], y: List[float]) -> float:
        n = min(len(x), len(y))
        if n < 5:
            return 0.0
        x, y = x[-n:], y[-n:]
        mx, my = sum(x) / n, sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return 0.0
        return cov / (sx * sy)

    def rolling_correlation(self, x: List[float], y: List[float], window: int = 20) -> List[float]:
        result = []
        n = min(len(x), len(y))
        for i in range(window, n + 1):
            result.append(self.pearson(x[i - window:i], y[i - window:i]))
        return result

    def lead_lag(self, x: List[float], y: List[float], max_lag: int = 10) -> Dict:
        """Find best lag (in bars) where x leads y. Returns {lag, correlation}."""
        best_lag, best_corr = 0, 0.0
        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                x_s, y_s = x[:len(x) - lag] if lag > 0 else x, y[lag:] if lag > 0 else y
            else:
                x_s, y_s = x[-lag:], y[:len(y) + lag]
            corr = abs(self.pearson(x_s, y_s))
            if corr > best_corr:
                best_corr, best_lag = corr, lag
        return {"best_lag": best_lag, "correlation": round(best_corr, 3),
                "interpretation": "x leads y" if best_lag > 0 else "y leads x" if best_lag < 0 else "synchronous"}

    def correlation_matrix(self, series: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
        names = list(series.keys())
        matrix: Dict[str, Dict[str, float]] = {}
        for a in names:
            matrix[a] = {}
            for b in names:
                matrix[a][b] = round(self.pearson(series[a], series[b]), 3)
        return matrix
