"""Strategy engine — pluggable strategies with uniform interface."""
from .base import Strategy, StrategyResult, SignalVote
from .registry import StrategyRegistry, get_registry, register_defaults
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .scalping import ScalpingStrategy
from .ichimoku_strategy import IchimokuStrategy
from .macd_rsi import MacdRsiStrategy
from .bollinger_squeeze import BollingerSqueezeStrategy
from .supply_demand import SupplyDemandStrategy
from .multi_tf_confluence import MultiTimeframeConfluence

__all__ = [
    "Strategy", "StrategyResult", "SignalVote",
    "StrategyRegistry", "get_registry", "register_defaults",
    "TrendFollowingStrategy", "MeanReversionStrategy", "BreakoutStrategy",
    "ScalpingStrategy", "IchimokuStrategy", "MacdRsiStrategy",
    "BollingerSqueezeStrategy", "SupplyDemandStrategy",
    "MultiTimeframeConfluence",
]
