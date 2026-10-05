"""Dashboard API routes."""
from __future__ import annotations
from flask import Flask, jsonify, request, Response
from functools import wraps

from ..config.settings import get_settings


def check_auth(username: str, password: str) -> bool:
    s = get_settings()
    return username == s.web_username and password == s.web_password


def authenticate():
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def register_routes(app: Flask) -> None:
    repo = lambda: app.config.get("repo")
    loop = lambda: app.config.get("scan_loop")

    @app.route("/")
    @requires_auth
    def index():
        from .static.index_html import INDEX_HTML
        return INDEX_HTML

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "xauusd-pro-bot"})

    @app.route("/api/signals")
    @requires_auth
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
    @requires_auth
    def status():
        r = repo()
        l = loop()
        stats = r.daily_stats() if r else {}
        return jsonify({
            "running": l.state.running if l else False,
            "last_scan_age": (
                __import__("time").time() - l.state.last_scan if l and l.state.last_scan else None
            ),
            "recent_signals_count": len(l.state.recent_signals) if l else 0,
            "daily": stats,
        })

    @app.route("/api/performance")
    @requires_auth
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
    @requires_auth
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
