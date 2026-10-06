"""Supply & Demand zones strategy — react from fresh zones."""
from __future__ import annotations
from typing import List, Tuple

from data.base import Candle
from .base import Strategy, StrategyResult


def _find_zones(candles: List[Candle], lookback: int = 100) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """Identify supply (resistance) and demand (support) zones from swing bases."""
    demand_zones: List[Tuple[float, float]] = []
    supply_zones: List[Tuple[float, float]] = []
    if len(candles) < 10:
        return demand_zones, supply_zones

    slice_c = candles[-lookback:] if len(candles) > lookback else candles
    for i in range(2, len(slice_c) - 2):
        c = slice_c[i]
        # Rally base (demand): small range candle before a big bullish candle
        if (slice_c[i + 1].close > slice_c[i + 1].open and
                slice_c[i + 1].body > c.body * 2 and
                c.range < slice_c[i + 1].range * 0.6):
            zone_low = min(c.low, slice_c[i + 1].low)
            zone_high = max(c.high, slice_c[i - 1].high)
            demand_zones.append((zone_low, zone_high))
        # Drop base (supply): small range candle before big bearish candle
        if (slice_c[i + 1].close < slice_c[i + 1].open and
                slice_c[i + 1].body > c.body * 2 and
                c.range < slice_c[i + 1].range * 0.6):
            zone_low = min(c.low, slice_c[i - 1].low)
            zone_high = max(c.high, slice_c[i + 1].high)
            supply_zones.append((zone_low, zone_high))
    return demand_zones[-5:], supply_zones[-5:]


class SupplyDemandStrategy(Strategy):
    name = "supply_demand"
    description = "Reversal entries at fresh supply/demand zones with RSI divergence."
    default_timeframes = ["15m", "1h", "4h"]

    def analyze(self, candles: List[Candle], timeframe: str = "") -> StrategyResult:
        result = StrategyResult(strategy=self.name)
        if len(candles) < 30:
            return result

        demand, supply = _find_zones(candles)
        price = candles[-1].close

        result.raw_indicators = {"demand_zones": demand, "supply_zones": supply, "price": price}

        # Check if price is inside a demand zone (buy) or supply zone (sell)
        for (zlo, zhi) in demand:
            if zlo <= price <= zhi:
                result.votes.append(self.vote_buy(
                    68, reasons=[f"At demand zone {zlo:.2f}-{zhi:.2f}"], timeframe=timeframe))
                return result
        for (zlo, zhi) in supply:
            if zlo <= price <= zhi:
                result.votes.append(self.vote_sell(
                    68, reasons=[f"At supply zone {zlo:.2f}-{zhi:.2f}"], timeframe=timeframe))
                return result

        # Near zone (within 0.3%) — anticipation
        for (zlo, zhi) in demand:
            if price < zlo and (zlo - price) / price < 0.003:
                result.votes.append(self.vote_buy(50, reasons=[f"Approaching demand {zlo:.2f}"], timeframe=timeframe))
                return result
        for (zlo, zhi) in supply:
            if price > zhi and (price - zhi) / price < 0.003:
                result.votes.append(self.vote_sell(50, reasons=[f"Approaching supply {zhi:.2f}"], timeframe=timeframe))
                return result

        result.votes.append(self.vote_neutral(reasons=["Away from key zones"], timeframe=timeframe))
        return result
