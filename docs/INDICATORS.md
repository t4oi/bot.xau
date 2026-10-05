# Indicators Library

The bot implements **25+ technical indicators** in pure Python (no TA-Lib dependency).

## Trend Indicators (indicators/trend.py)
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
- WMA (Weighted Moving Average)
- HMA (Hull Moving Average)
- Ichimoku Kinko Hyo (Tenkan, Kijun, Senkou A/B, Chikou)
- ADX / +DI / -DI (Average Directional Index)
- Parabolic SAR
- Supertrend
- VWAP (anchored)

## Momentum Oscillators (indicators/momentum.py)
- RSI (Relative Strength Index, Wilder smoothing)
- MACD (line, signal, histogram) + cross detection
- Stochastic (%K, %D)
- CCI (Commodity Channel Index)
- Williams %R
- ROC (Rate of Change)
- MFI (Money Flow Index)
- Awesome Oscillator
- RSI Divergence detector

## Volatility (indicators/volatility.py)
- Bollinger Bands (middle, upper, lower, %B, bandwidth)
- ATR (Average True Range, Wilder)
- Keltner Channels
- Donchian Channels
- Standard Deviation (rolling)
- Chandelier Exit (long/short)
- Volatility Ratio (short/long ATR)

## Volume (indicators/volume.py)
- OBV (On-Balance Volume)
- VWAP
- Accumulation/Distribution Line
- Volume Profile (POC, Value Area)
- Money Flow + state classification
- Volume Spike detector

## Candlestick Patterns (indicators/candlestick.py)
15+ patterns: Doji, Marubozu, Hammer, Shooting Star, Engulfing (bull/bear), Harami, Piercing Pattern, Dark Cloud Cover, Morning Star, Evening Star, Three White Soldiers, Three Black Crows. Each has a bullish/bearish score for confluence.

## Fibonacci & Pivots (indicators/fibonacci.py)
- Fibonacci retracement (0.236, 0.382, 0.5, 0.618, 0.786)
- Fibonacci extension (1.272, 1.618, 2.0, 2.618...)
- Pivot points: Classic, Woodie, Camarilla, Fibonacci
- Swing point detection
- Nearest level finder

All indicators accept lists of floats/candles and return lists aligned to input length with NaN for warmup periods.
