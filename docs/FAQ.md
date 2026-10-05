# FAQ

## Q: How do I change the risk per trade?
Edit `.env`: `RISK_PER_TRADE_PCT=1.0` (1% of balance). Restart the bot.

## Q: How do I get more/fewer signals?
- Lower `MIN_CONFLUENCE_SCORE` (e.g., 55) → more signals, lower quality.
- Raise it (e.g., 75) → fewer, higher quality.
- Adjust `SIGNAL_COOLDOWN_MINUTES`.
- Switch profile: use `AGGRESSIVE` for scalping frequency.

## Q: Why no signal was sent?
Check logs. Common reasons: spread too wide, R:R below threshold, confluence below threshold, cooldown active, daily loss limit hit, market closed (weekend).

## Q: How do I backtest?
```bash
python run.py --backtest
python -m cli.main backtest --timeframe 1h --limit 1000 --montecarlo --mc-sims 1000
```

## Q: Can I add my own strategy?
Yes. Subclass `strategies/base.py:Strategy`, implement `analyze()`, return `StrategyResult` with votes. Register it in `strategies/registry.py`. It automatically participates in confluence scoring.

## Q: Does the bot actually place trades?
No. This is a **signal bot** — it analyzes and sends signals to Telegram. You execute manually (or connect to a broker API via the `execution/` package as a starting point).

## Q: What data source does it use?
BiQuote.io API (`https://biquote.io/api`). Extendable via `data/providers_extra.py` (CSV, generic REST, fallback router).

## Q: How accurate are the signals?
No guarantee. Always backtest and demo-trade first. Past performance ≠ future results. The bot includes a full backtest + Monte Carlo + Walk-Forward suite to evaluate strategies objectively.
