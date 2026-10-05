"""Tests for ML module."""
import pytest
from xauusd_pro_bot.ml.features import FeatureEngineer
from xauusd_pro_bot.ml.model import SignalPredictor
from xauusd_pro_bot.data.base import Candle


def _candles(n=100):
    import random
    rng = random.Random(42)
    price = 2000
    out = []
    for i in range(n):
        price += rng.uniform(-2, 2)
        out.append(Candle(time=str(i), open=price-0.5, high=price+1, low=price-1,
                          close=price, volume=rng.uniform(500, 2000)))
    return out


def test_feature_engineer_extracts():
    eng = FeatureEngineer()
    candles = _candles(100)
    feats = eng.extract(candles)
    assert feats is not None
    assert len(feats) == len(FeatureEngineer.FEATURE_NAMES)
    vec = eng.to_vector(feats)
    assert len(vec) == len(FeatureEngineer.FEATURE_NAMES)


def test_signal_predictor_untrained():
    model = SignalPredictor(n_features=29)
    pred, conf = model.predict([0.0] * 29)
    assert pred in (-1, 0, 1)
    assert 0 <= conf <= 1


def test_signal_predictor_train():
    import random
    rng = random.Random(42)
    X = [[rng.uniform(-1, 1) for _ in range(29)] for _ in range(200)]
    y = [1 if sum(x) > 0 else -1 if sum(x) < -2 else 0 for x in X]
    model = SignalPredictor(n_features=29, iterations=100)
    info = model.train(X, y)
    assert info.get("trained") is True
    pred, conf = model.predict(X[0])
    assert pred in (-1, 0, 1)
