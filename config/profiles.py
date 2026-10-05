"""Strategy profiles — pre-configured parameter sets for different market conditions."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StrategyProfile:
    name: str
    description: str
    enabled_strategies: List[str]
    min_confluence: float
    timeframes: List[str]
    primary_timeframe: str
    risk_per_trade_pct: float
    atr_sl_multiplier: float
    tp_multipliers: List[float]
    cooldown_minutes: int
    notes: str = ""


# Conservative profile — high confluence, larger SL, fewer signals
CONSERVATIVE = StrategyProfile(
    name="conservative",
    description="High-confluence, low-frequency trading. Best for volatile markets.",
    enabled_strategies=["trend_following", "ichimoku", "supply_demand", "smart_money", "momentum_divergence"],
    min_confluence=75.0,
    timeframes=["15m", "1h", "4h"],
    primary_timeframe="1h",
    risk_per_trade_pct=0.5,
    atr_sl_multiplier=2.0,
    tp_multipliers=[2.0, 4.0, 6.0],
    cooldown_minutes=60,
    notes="Only takes highest-quality setups. Expect 1-3 signals/day.",
)

# Balanced profile — default
BALANCED = StrategyProfile(
    name="balanced",
    description="Default balanced profile. Good all-around performance.",
    enabled_strategies=["trend_following", "mean_reversion", "breakout", "ichimoku",
                        "macd_rsi", "bollinger_squeeze", "supply_demand", "smart_money",
                        "momentum_divergence", "harmonic", "volume_spread"],
    min_confluence=65.0,
    timeframes=["5m", "15m", "30m", "1h", "4h"],
    primary_timeframe="15m",
    risk_per_trade_pct=1.0,
    atr_sl_multiplier=1.5,
    tp_multipliers=[1.5, 3.0, 5.0],
    cooldown_minutes=30,
    notes="Good balance between frequency and quality.",
)

# Aggressive profile — scalping, lower confluence
AGGRESSIVE = StrategyProfile(
    name="aggressive",
    description="High-frequency scalping. Higher risk, more signals.",
    enabled_strategies=["scalping", "mean_reversion", "macd_rsi", "bollinger_squeeze",
                        "momentum_divergence", "volume_spread"],
    min_confluence=55.0,
    timeframes=["1m", "5m", "15m"],
    primary_timeframe="5m",
    risk_per_trade_pct=0.5,
    atr_sl_multiplier=1.0,
    tp_multipliers=[1.0, 1.5, 2.5],
    cooldown_minutes=10,
    notes="Many signals (10+/day). Requires tight risk management.",
)

# Trend-following profile — for strong trending markets
TREND_FOLLOWING = StrategyProfile(
    name="trend_following",
    description="Optimized for strong trending markets.",
    enabled_strategies=["trend_following", "breakout", "ichimoku", "supertrend" if False else "trend_following",
                        "smart_money"],
    min_confluence=60.0,
    timeframes=["15m", "1h", "4h"],
    primary_timeframe="1h",
    risk_per_trade_pct=1.0,
    atr_sl_multiplier=2.5,
    tp_multipliers=[2.0, 4.0, 7.0],
    cooldown_minutes=45,
    notes="Ride trends with wide stops. Best when ADX > 25.",
)

# Range-bound profile — for sideways markets
RANGE_BOUND = StrategyProfile(
    name="range_bound",
    description="Optimized for ranging/sideways markets (mean reversion).",
    enabled_strategies=["mean_reversion", "bollinger_squeeze", "supply_demand",
                        "harmonic", "volume_spread"],
    min_confluence=60.0,
    timeframes=["5m", "15m", "1h"],
    primary_timeframe="15m",
    risk_per_trade_pct=0.75,
    atr_sl_multiplier=1.2,
    tp_multipliers=[1.2, 2.0, 3.0],
    cooldown_minutes=20,
    notes="Buy support, sell resistance. Best when ADX < 20.",
)

PROFILES: Dict[str, StrategyProfile] = {
    p.name: p for p in [CONSERVATIVE, BALANCED, AGGRESSIVE, TREND_FOLLOWING, RANGE_BOUND]
}


def get_profile(name: str) -> StrategyProfile:
    if name not in PROFILES:
        raise KeyError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return PROFILES[name]


def list_profiles() -> List[str]:
    return list(PROFILES.keys())


def auto_select_profile(adx_value: float, regime: str = "") -> StrategyProfile:
    """Auto-select profile based on market regime (ADX)."""
    if adx_value >= 25 or regime in ("TRENDING_UP", "TRENDING_DOWN"):
        return TREND_FOLLOWING
    if adx_value < 18 or regime == "RANGING":
        return RANGE_BOUND
    return BALANCED
