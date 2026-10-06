"""Dashboard API routes — NO authentication (open access as requested)."""
from __future__ import annotations
from flask import Flask, jsonify, request


def register_routes(app: Flask) -> None:
    repo = lambda: app.config.get("repo")
    loop = lambda: app.config.get("scan_loop")

    @app.route("/")
    def index():
        from .static.index_html import INDEX_HTML
        return INDEX_HTML

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "xauusd-pro-bot"})

    @app.route("/api/signals")
    def signals():
        r = repo()
        if not r:
            return jsonify([])
        limit = int(request.args.get("limit", 20))
        recs = r.recent_signals(limit)
        return jsonify([{
            "id": s.signal_id, "symbol": s.symbol, "direction": s.direction,
            "entry": s.entry, "stop_loss": s.stop_loss, "take_profits": s.take_profits,
            "confluence": s.confluence_pct, "timeframe": s.timeframe,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "outcome": s.outcome,
        } for s in recs])

    @app.route("/api/status")
    def status():
        r = repo()
        l = loop()
        stats = r.daily_stats() if r else {}
        import time as _time
        return jsonify({
            "running": l.state.running if l else False,
            "last_scan_age": (_time.time() - l.state.last_scan) if l and l.state.last_scan else None,
            "recent_signals_count": len(l.state.recent_signals) if l else 0,
            "daily": stats,
        })

    @app.route("/api/performance")
    def performance():
        r = repo()
        if not r:
            return jsonify([])
        days = int(request.args.get("days", 30))
        snaps = r.performance_history(days)
        return jsonify([{
            "timestamp": s.timestamp.isoformat() if s.timestamp else "",
            "signals": s.total_signals, "trades": s.total_trades,
            "win_rate": s.win_rate_pct, "pnl": s.total_pnl_usd,
            "max_dd": s.max_drawdown_pct, "pf": s.profit_factor,
        } for s in snaps])

    @app.route("/api/trades/open")
    def open_trades():
        r = repo()
        if not r:
            return jsonify([])
        trades = r.open_trades()
        return jsonify([{
            "signal_id": t.signal_id, "symbol": t.symbol, "direction": t.direction,
            "entry": t.entry_price, "sl": t.stop_loss, "tp": t.take_profit,
            "lot": t.lot_size, "opened_at": t.opened_at.isoformat() if t.opened_at else "",
        } for t in trades])
