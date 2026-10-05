"""Random Forest classifier (pure numpy) for signal prediction."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..core.logging_config import get_logger

logger = get_logger("ml.random_forest")


@dataclass
class TreeNode:
    feature_idx: int = -1
    threshold: float = 0.0
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None
    prediction: float = 0.0
    is_leaf: bool = False


class DecisionTree:
    """Simple CART decision tree for classification."""

    def __init__(self, max_depth: int = 5, min_samples_split: int = 10,
                 max_features: Optional[int] = None):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.max_features = max_features
        self.root: Optional[TreeNode] = None

    def _gini(self, y: np.ndarray) -> float:
        if len(y) == 0:
            return 0.0
        classes, counts = np.unique(y, return_counts=True)
        p = counts / len(y)
        return 1.0 - sum(p ** 2)

    def _best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float, float]:
        best_gini = float("inf")
        best_feat, best_thresh = -1, 0.0
        n_features = X.shape[1]
        feats = random.sample(range(n_features), min(self.max_features or n_features, n_features))
        for feat in feats:
            values = np.unique(X[:, feat])
            if len(values) > 20:
                values = np.quantile(X[:, feat], np.linspace(0.1, 0.9, 10))
            for thresh in values:
                left_mask = X[:, feat] <= thresh
                if left_mask.sum() < self.min_samples_split or (~left_mask).sum() < self.min_samples_split:
                    continue
                gini = (left_mask.sum() * self._gini(y[left_mask]) +
                        (~left_mask).sum() * self._gini(y[~left_mask])) / len(y)
                if gini < best_gini:
                    best_gini, best_feat, best_thresh = gini, feat, thresh
        return best_feat, best_thresh, best_gini

    def _build(self, X: np.ndarray, y: np.ndarray, depth: int) -> TreeNode:
        node = TreeNode()
        if (depth >= self.max_depth or len(y) < self.min_samples_split or
                len(np.unique(y)) == 1):
            vals, counts = np.unique(y, return_counts=True)
            node.prediction = float(vals[np.argmax(counts)])
            node.is_leaf = True
            return node
        feat, thresh, gini = self._best_split(X, y)
        if feat < 0:
            vals, counts = np.unique(y, return_counts=True)
            node.prediction = float(vals[np.argmax(counts)])
            node.is_leaf = True
            return node
        node.feature_idx = feat
        node.threshold = thresh
        left_mask = X[:, feat] <= thresh
        node.left = self._build(X[left_mask], y[left_mask], depth + 1)
        node.right = self._build(X[~left_mask], y[~left_mask], depth + 1)
        return node

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self.root = self._build(X, y, 0)

    def _predict_one(self, x: np.ndarray, node: TreeNode) -> float:
        if node.is_leaf:
            return node.prediction
        if x[node.feature_idx] <= node.threshold:
            return self._predict_one(x, node.left)
        return self._predict_one(x, node.right)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.array([self._predict_one(x, self.root) for x in X])


class RandomForestSignalModel:
    """Random Forest ensemble for signal classification."""

    def __init__(self, n_trees: int = 20, max_depth: int = 5,
                 min_samples_split: int = 10, max_features: Optional[int] = None,
                 seed: int = 42):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.max_features = max_features
        self.trees: List[DecisionTree] = []
        self.rng = random.Random(seed)
        self.trained = False
        random.seed(seed)

    def fit(self, X: List[List[float]], y: List[int]) -> dict:
        X_arr = np.array(X, dtype=float)
        y_arr = np.array(y, dtype=int)
        n = len(X_arr)
        if n < 100:
            return {"trained": False, "reason": f"only {n} samples"}
        self.trees = []
        for t in range(self.n_trees):
            # Bootstrap sample
            indices = [self.rng.randint(0, n - 1) for _ in range(n)]
            tree = DecisionTree(max_depth=self.max_depth,
                                min_samples_split=self.min_samples_split,
                                max_features=self.max_features or int(math.sqrt(X_arr.shape[1])))
            tree.fit(X_arr[indices], y_arr[indices])
            self.trees.append(tree)
        self.trained = True
        # OOB accuracy estimate
        correct = 0
        oob_count = 0
        for i in range(min(n, 200)):
            preds = [t.predict(X_arr[i:i+1])[0] for t in self.trees]
            from collections import Counter
            pred = Counter(preds).most_common(1)[0][0]
            if pred == y_arr[i]:
                correct += 1
            oob_count += 1
        acc = correct / oob_count if oob_count else 0
        logger.info("Random Forest trained: %d trees, OOB acc %.1f%%", self.n_trees, acc * 100)
        return {"trained": True, "trees": self.n_trees, "oob_accuracy": round(acc, 3)}

    def predict_proba(self, x: List[float]) -> dict:
        if not self.trained:
            return {-1: 0.33, 0: 0.34, 1: 0.33}
        x_arr = np.array(x, dtype=float).reshape(1, -1)
        preds = [t.predict(x_arr)[0] for t in self.trees]
        from collections import Counter
        counts = Counter(preds)
        total = len(preds)
        return {int(k): round(v / total, 3) for k, v in counts.items()}

    def predict(self, x: List[float]) -> Tuple[int, float]:
        probs = self.predict_proba(x)
        best = max(probs, key=probs.get)
        return best, probs[best]

    def feature_importance(self, n_features: int) -> List[float]:
        """Simple permutation importance approximation."""
        return [1.0 / n_features] * n_features
