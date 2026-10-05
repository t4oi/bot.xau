# Risk Management

## Position Sizing (risk/position_sizer.py)
Lot size = (Account Balance × Risk%) / (SL distance × $100 per $1 per lot)
- XAUUSD contract: 1 lot = 100 oz → $100 P&L per $1 price move per lot.
- Min lot 0.01, max lot configurable.

## Risk Limits (risk/limits.py)
- **Max daily losses**: halt trading after N losses (default 3).
- **Max daily loss %**: halt after N% daily drawdown (default 5%).
- **Max drawdown %**: global halt after N% peak-to-trough (default 15%).
- **Max signals per day**: cap signal frequency (default 20).
- **Cooldown**: minimum minutes between signals (default 30).

## Drawdown Guard (risk/drawdown_guard.py)
- Tracks equity curve peak.
- Dynamically reduces risk multiplier as drawdown deepens (halving every 5% DD step).
- Computes recovery factor and max drawdown.

## Session Manager (risk/session_manager.py)
- Identifies current session (Asia/London/NY/Overlap/Pacific) in UTC.
- Applies volatility multiplier per session.
- Preferred sessions (London, NY, Overlap) get higher signal weight.
- Weekend market closed detection.

## Signal Filters (signal/filters.py)
- Spread filter (reject if spread > 0.50).
- Minimum R:R filter (default 1:1.5).
- Minimum confluence filter (default 65%).
- Cooldown filter.
- Session awareness (soft).

## Execution Cost Modeling (execution/slippage.py)
- Slippage: 0.05% + random component.
- Dynamic spread based on session + ATR.
- Commission per lot.
- Applied in backtest for realistic results.

## ⚠️ Disclaimer
No risk system eliminates loss. Always test on demo first and never risk more than you can afford to lose.
