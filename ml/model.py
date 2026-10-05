"""Lightweight ML models — logistic regression + random forest (pure Python-ish via numpy)."""
from __future__ import annotations
import math
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.logging_config import get_logger

logger = get_logger("ml.model")


class SignalPredictor:
    """Logistic regression classifier trained on engineered features."""

    def __init__(self, n_features: int = 29, learning_rate: float = 0.01,
                 iterations: int = 1000, regularization: float = 0.01):
        self.n_features = n_features
        self.lr = learning_rate
        self.iterations = iterations
        self.reg = regularization
        self.weights: Optional[np.ndarray] = None
        self.bias: float = 0.0
        self.scaler_mean: Optional[np.ndarray] = None
        self.scaler_std: Optional[np.ndarray] = None
        self.trained = False
        self.classes_ = [-1, 0, 1]

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

    def _scale(self, X: np.ndarray, fit: bool = False) -> np.ndarray:
        if fit:
            self.scaler_mean = X.mean(axis=0)
            self.scaler_std = X.std(axis=0) + 1e-8
        return (X - self.scaler_mean) / self.scaler_std

    def train(self, X: List[List[float]], y: List[int]) -> Dict:
        """One-vs-rest logistic regression (3 classes)."""
        X_arr = np.array(X, dtype=float)
        y_arr = np.array(y, dtype=int)
        if len(X_arr) < 50:
            logger.warning("Not enough samples (%d) to train ML model", len(X_arr))
            return {"samples": len(X_arr), "trained": False}

        X_scaled = self._scale(X_arr, fit=True)
        # One-vs-rest: train 3 binary classifiers
        self.weights = np.zeros((3, self.n_features))
        self.biases = np.zeros(3)
        class_map = {-1: 0, 0: 1, 1: 2}
        losses = []

        for cls_idx, cls_val in enumerate([-1, 0, 1]):
            y_binary = (y_arr == cls_val).astype(float)
            w = np.zeros(self.n_features)
            b = 0.0
            for it in range(self.iterations):
                z = X_scaled @ w + b
                pred = self._sigmoid(z)
                grad_w = X_scaled.T @ (pred - y_binary) / len(y_binary) + self.reg * w
                grad_b = (pred - y_binary).mean()
                w -= self.lr * grad_w
                b -= self.lr * grad_b
                if it % 200 == 0:
                    loss = -np.mean(y_binary * np.log(pred + 1e-10) +
                                    (1 - y_binary) * np.log(1 - pred + 1e-10))
                    losses.append(float(loss))
            self.weights[cls_idx] = w
            self.biases[cls_idx] = b

        self.trained = True
        train_acc = self._accuracy(X_scaled, y_arr)
        logger.info("ML model trained: %d samples, train acc %.1f%%", len(X_arr), train_acc * 100)
        return {"samples": len(X_arr), "train_accuracy": round(train_acc, 3),
                "final_loss": losses[-1] if losses else 0, "trained": True}

    def _accuracy(self, X_scaled: np.ndarray, y: np.ndarray) -> float:
        logits = X_scaled @ self.weights.T + self.biases
        preds = np.argmax(logits, axis=1) - 1
        return float((preds == y).mean())

    def predict_proba(self, features: List[float]) -> Dict[int, float]:
        if not self.trained or self.weights is None:
            return {-1: 0.33, 0: 0.34, 1: 0.33}
        x = np.array(features, dtype=float).reshape(1, -1)
        x_scaled = self._scale(x)
        logits = x_scaled @ self.weights.T + self.biases
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        return {-1: float(probs[0][0]), 0: float(probs[0][1]), 1: float(probs[0][2])}

    def predict(self, features: List[float]) -> Tuple[int, float]:
        probs = self.predict_proba(features)
        best = max(probs, key=probs.get)
        return best, probs[best]

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"weights": self.weights, "biases": getattr(self, "biases", None),
                         "mean": self.scaler_mean, "std": self.scaler_std,
                         "trained": self.trained}, f)

    def load(self, path: str) -> bool:
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.weights = data["weights"]
            self.biases = data["biases"]
            self.scaler_mean = data["mean"]
            self.scaler_std = data["std"]
            self.trained = data["trained"]
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load ML model: %s", exc)
            return False


class ModelTrainer:
    """Trains and validates the ML predictor with walk-forward splits."""

    def __init__(self, test_ratio: float = 0.2):
        self.test_ratio = test_ratio

    def train_and_evaluate(self, X: List[List[float]], y: List[int]) -> Dict:
        split = int(len(X) * (1 - self.test_ratio))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        model = SignalPredictor(n_features=len(X[0]) if X else 29)
        train_info = model.train(X_train, y_train)
        # Evaluate on test
        correct = 0
        for xi, yi in zip(X_test, y_test):
            pred, _ = model.predict(xi)
            if pred == yi:
                correct += 1
        test_acc = correct / len(X_test) if X_test else 0
        return {"model": model, "train": train_info,
                "test_accuracy": round(test_acc, 3),
                "test_samples": len(X_test)}
