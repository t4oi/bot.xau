"""ML scorer — integrates ML prediction into the signal pipeline."""
from __future__ import annotations
from typing import Dict, List, Optional

from ..config.constants import SignalDirection
from ..core.logging_config import get_logger
from ..data.base import Candle
from .features import FeatureEngineer
from .model import SignalPredictor

logger = get_logger("ml.scorer")


class MLScorer:
    """Adds an ML-based confidence score to signals."""

    def __init__(self, model: Optional[SignalPredictor] = None,
                 engineer: Optional[FeatureEngineer] = None):
        self.engineer = engineer or FeatureEngineer()
        self.model = model or SignalPredictor(n_features=len(self.engineer.FEATURE_NAMES))
        self.model_path = "./data/ml_model.pkl"

    def score(self, candles: List[Candle]) -> Dict:
        """Return {direction, confidence, probs} from ML model."""
        features = self.engineer.extract(candles)
        if features is None:
            return {"direction": SignalDirection.NEUTRAL, "confidence": 0.0,
                    "probs": {}, "available": False}
        vector = self.engineer.to_vector(features)
        if not self.model.trained:
            if self.model.load(self.model_path):
                logger.info("Loaded pre-trained ML model")
            else:
                return {"direction": SignalDirection.NEUTRAL, "confidence": 0.0,
                        "probs": {}, "available": False, "note": "model not trained"}
        pred, conf = self.model.predict(vector)
        probs = self.model.predict_proba(vector)
        direction = SignalDirection.BUY if pred == 1 else SignalDirection.SELL if pred == -1 else SignalDirection.NEUTRAL
        return {
            "direction": direction,
            "confidence": round(conf * 100, 1),
            "probs": {str(k): round(v, 3) for k, v in probs.items()},
            "available": True,
        }

    def train_on_history(self, candles: List[Candle]) -> Dict:
        """Train the ML model on historical candles."""
        X, y = self.engineer.build_dataset(candles, forward_bars=5, threshold_pct=0.3)
        if len(X) < 100:
            return {"trained": False, "reason": f"only {len(X)} samples"}
        info = self.model.train(X, y)
        if info.get("trained"):
            self.model.save(self.model_path)
            logger.info("ML model trained and saved to %s", self.model_path)
        return info
