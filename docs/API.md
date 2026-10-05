# Web Dashboard API

## Authentication
All `/api/*` routes (except `/api/health`) require HTTP Basic Auth.
- Username: `WEB_USERNAME` (default `admin`)
- Password: `WEB_PASSWORD` (default `changeme123` — **change this**)

## Endpoints

### GET /api/health
Public health check. Returns `{"status": "ok"}`.

### GET /api/status
Returns bot runtime status:
```json
{
  "running": true,
  "last_scan_age": 45.2,
  "recent_signals_count": 12,
  "daily": {"signals_sent": 5, "wins": 3, "losses": 1, "pnl": 45.5, "win_rate": 75.0}
}
```

### GET /api/signals?limit=20
Recent signals with entry/SL/TPs/confluence/timeframe/outcome.

### GET /api/performance?days=30
Performance snapshots history for charts.

### GET /api/trades/open
Currently open positions with entry/SL/TP/lot.

## Dashboard UI
- Dark theme, RTL Arabic support.
- Live stats cards (signals today, wins, PnL, last scan age).
- Recent signals table with confluence bars.
- 30-day performance summary grid.
- Auto-refresh every 30 seconds.

## Running
```bash
python run.py --web-only   # dashboard only
python run.py              # full bot + dashboard on :8080
```
