"""Feature engineering — builds feature vectors from candles for ML models."""
from __future__ import annotations
import math
from typing import Dict, List, Optional

from data.base import Candle
from indicators.trend import ema, sma, adx
from indicators.momentum import rsi, macd, stochastic, roc, cci, williams_r
from indicators.volatility import bollinger_bands, average_true_range, standard_deviation


class FeatureEngineer:
    """Builds a feature vector from OHLCV candles."""

    FEATURE_NAMES = [
        "rsi_14", "rsi_7", "macd_hist", "macd_line", "stoch_k", "stoch_d",
        "ema20_slope", "ema50_slope", "price_vs_ema20", "price_vs_ema50",
        "adx_14", "plus_di", "minus_di", "atr_pct", "bb_pctb", "bb_width",
        "roc_12", "cci_20", "williams_r", "body_ratio", "upper_wick_ratio",
        "lower_wick_ratio", "volume_ratio", "range_pct", "close_position",
        "candle_bullish", "momentum_5", "momentum_10", "volatility_ratio",
    ]

    def __init__(self, lookback: int = 200):
        self.lookback = lookback

    def extract(self, candles: List[Candle]) -> Optional[Dict[str, float]]:
        """Extract features from the latest point in the series."""
        if len(candles) < 60:
            return None
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        last = candles[-1]
        price = last.close

        rsi14 = rsi(closes, 14)[-1]
        rsi7 = rsi(closes, 7)[-1]
        macd_line, signal_line, hist = macd(closes)
        k, d = stochastic(highs, lows, closes)
        e20 = ema(closes, 20)
        e50 = ema(closes, 50)
        adx_vals, plus_di, minus_di = adx(highs, lows, closes, 14)
        atr = average_true_range(highs, lows, closes, 14)[-1]
        bb_mid, bb_up, bb_lo, pctb = bollinger_bands(closes, 20, 2.0)
        bw = [(u - l) / m * 100 if m and not math.isnan(m) and m != 0 else 0
              for u, l, m in zip(bb_up, bb_lo, bb_mid)]
        roc12 = roc(closes, 12)[-1]
        cci20 = cci(highs, lows, closes, 20)[-1]
        wr = williams_r(highs, lows, closes, 14)[-1]
        vol_avg = sum(volumes[-20:-1]) / 19 if len(volumes) >= 20 else 1

        def safe(v):
            return 0.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v

        features = {
            "rsi_14": safe(rsi14), "rsi_7": safe(rsi7),
            "macd_hist": safe(hist[-1]), "macd_line": safe(macd_line[-1]),
            "stoch_k": safe(k[-1]), "stoch_d": safe(d[-1]),
            "ema20_slope": safe(e20[-1] - e20[-5]) if len(e20) >= 5 else 0,
            "ema50_slope": safe(e50[-1] - e50[-5]) if len(e50) >= 5 else 0,
            "price_vs_ema20": (price - safe(e20[-1])) / price * 100 if price else 0,
            "price_vs_ema50": (price - safe(e50[-1])) / price * 100 if price else 0,
            "adx_14": safe(adx_vals[-1]), "plus_di": safe(plus_di[-1]),
            "minus_di": safe(minus_di[-1]),
            "atr_pct": safe(atr) / price * 100 if price else 0,
            "bb_pctb": safe(pctb[-1]), "bb_width": safe(bw[-1]),
            "roc_12": safe(roc12), "cci_20": safe(cci20), "williams_r": safe(wr),
            "body_ratio": last.body / last.range if last.range > 0 else 0,
            "upper_wick_ratio": (last.high - max(last.open, last.close)) / last.range if last.range > 0 else 0,
            "lower_wick_ratio": (min(last.open, last.close) - last.low) / last.range if last.range > 0 else 0,
            "volume_ratio": last.volume / vol_avg if vol_avg > 0 else 1,
            "range_pct": last.range / price * 100 if price else 0,
            "close_position": (last.close - last.low) / last.range if last.range > 0 else 0.5,
            "candle_bullish": 1.0 if last.is_bullish else 0.0,
            "momentum_5": (price - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 and closes[-6] else 0,
            "momentum_10": (price - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 and closes[-11] else 0,
            "volatility_ratio": safe(atr) / (sum(abs(closes[i]-closes[i-1]) for i in range(-20, -1)) / 19 or 1),
        }
        return features

    def to_vector(self, features: Dict[str, float]) -> List[float]:
        return [features.get(name, 0.0) for name in self.FEATURE_NAMES]

    def build_dataset(self, candles: List[Candle], forward_bars: int = 5,
                      threshold_pct: float = 0.3) -> tuple:
        """Build (X, y) dataset. y=1 if price rises > threshold in forward_bars."""
        X, y = [], []
        for i in range(self.lookback, len(candles) - forward_bars):
            feats = self.extract(candles[:i + 1])
            if feats is None:
                continue
            future_return = (candles[i + forward_bars].close - candles[i].close) / candles[i].close * 100
            if future_return > threshold_pct:
                label = 1
            elif future_return < -threshold_pct:
                label = -1
            else:
                label = 0
            X.append(self.to_vector(feats))
            y.append(label)
        return X, y
