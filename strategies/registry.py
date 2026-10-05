"""Strategy registry — pluggable, discoverable strategies."""
from __future__ import annotations
from typing import Dict, List, Optional, Type

from ..core.logging_config import get_logger
from .base import Strategy

logger = get_logger("strategies.registry")


class StrategyRegistry:
    """Central registry mapping strategy name -> class."""

    def __init__(self):
        self._strategies: Dict[str, Type[Strategy]] = {}
        self._instances: Dict[str, Strategy] = {}

    def register(self, strategy_cls: Type[Strategy]) -> Type[Strategy]:
        name = strategy_cls.name
        if name in self._strategies:
            logger.warning("Overwriting registered strategy: %s", name)
        self._strategies[name] = strategy_cls
        return strategy_cls

    def get(self, name: str, params: Optional[dict] = None) -> Strategy:
        if name not in self._strategies:
            raise KeyError(f"Unknown strategy: {name}. Available: {list(self._strategies)}")
        key = f"{name}:{str(sorted((params or {}).items()))}"
        if key not in self._instances:
            self._instances[key] = self._strategies[name](params=params)
        return self._instances[key]

    def all_names(self) -> List[str]:
        return sorted(self._strategies.keys())

    def create_all(self, enabled: Optional[List[str]] = None) -> List[Strategy]:
        names = enabled or self.all_names()
        return [self.get(n) for n in names if n in self._strategies]

    def __contains__(self, name: str) -> bool:
        return name in self._strategies

    def __len__(self) -> int:
        return len(self._strategies)


_GLOBAL_REGISTRY: Optional[StrategyRegistry] = None


def get_registry() -> StrategyRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = StrategyRegistry()
        register_defaults(_GLOBAL_REGISTRY)
    return _GLOBAL_REGISTRY


def register_defaults(registry: StrategyRegistry) -> None:
    """Register all built-in strategies."""
    from .trend_following import TrendFollowingStrategy
    from .mean_reversion import MeanReversionStrategy
    from .breakout import BreakoutStrategy
    from .scalping import ScalpingStrategy
    from .ichimoku_strategy import IchimokuStrategy
    from .macd_rsi import MacdRsiStrategy
    from .bollinger_squeeze import BollingerSqueezeStrategy
    from .supply_demand import SupplyDemandStrategy
    from .advanced_strategies import (
        MomentumDivergenceStrategy, SmartMoneyConceptsStrategy,
        HarmonicPatternStrategy, VolumeSpreadStrategy,
    )
    from .library_extra import (
        KeltnerBounceStrategy, VWAPBounceStrategy, EMARibbonStrategy,
        HeikinAshiStrategy, TripleScreenStrategy, SupertrendStrategy,
    )
    for cls in (TrendFollowingStrategy, MeanReversionStrategy, BreakoutStrategy,
                ScalpingStrategy, IchimokuStrategy, MacdRsiStrategy,
                BollingerSqueezeStrategy, SupplyDemandStrategy,
                MomentumDivergenceStrategy, SmartMoneyConceptsStrategy,
                HarmonicPatternStrategy, VolumeSpreadStrategy,
                KeltnerBounceStrategy, VWAPBounceStrategy, EMARibbonStrategy,
                HeikinAshiStrategy, TripleScreenStrategy, SupertrendStrategy):
        registry.register(cls)
    logger.info("Registered %d default strategies", len(registry))
