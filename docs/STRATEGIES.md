# Strategies Documentation

## Overview
The bot ships with **12 pluggable strategies** across 4 categories:

### Trend Following (trend_following)
- **Logic**: EMA20 > EMA50 > EMA200 bullish stack, ADX >= 25 confirms trend strength, pullback to EMA20 entry, Supertrend filter.
- **Best TF**: 15m, 1h, 4h
- **Confidence range**: 55-90

### Mean Reversion (mean_reversion)
- **Logic**: RSI < 30 oversold + touch lower Bollinger Band + Stochastic turning up = BUY. Opposite for SELL.
- **Best TF**: 5m, 15m, 1h

### Breakout (breakout)
- **Logic**: Close above/below 20-period Donchian channel + volume spike + volatility squeeze confirmation.
- **Best TF**: 15m, 1h, 4h

### Scalping (scalping)
- **Logic**: EMA5/EMA13 cross + RSI(7) neutral zone + Stochastic cross + MACD histogram momentum.
- **Best TF**: 1m, 5m
- **Note**: Higher frequency, lower per-trade R:R.

### Ichimoku (ichimoku)
- **Logic**: Price vs Cloud, Tenkan/Kijun cross, Senkou span color, Chikou confirmation. Score-based.
- **Best TF**: 15m, 1h, 4h

### MACD+RSI (macd_rsi)
- **Logic**: MACD crossover confirmed by RSI direction (not overbought/oversold).

### Bollinger Squeeze (bollinger_squeeze)
- **Logic**: BB inside Keltner = squeeze; trade breakout direction when released.

### Supply/Demand (supply_demand)
- **Logic**: Identify fresh demand/supply zones from swing bases; trade reactions at zones.

### Momentum Divergence (momentum_divergence)
- **Logic**: RSI bullish/bearish divergence against price. Counter-trend entries.

### Smart Money Concepts (smart_money)
- **Logic**: Fair Value Gaps (FVG), liquidity sweeps, order block reactions.

### Harmonic Patterns (harmonic)
- **Logic**: Simplified Gartley/Butterfly pattern detection via swing point ratios.

### Volume Spread (volume_spread)
- **Logic**: Wyckoff method — no demand/no supply bars, climactic volume, effort vs result.

## Confluence Scoring
Each strategy votes with a confidence (0-100). Votes are weighted by timeframe (higher TF = more weight). Net score determines direction. Signal sent only if confluence >= configured threshold (default 65%).

## Profile Auto-Selection
Use `config/profiles.py` to switch between Conservative / Balanced / Aggressive / Trend / Range profiles based on ADX regime.
