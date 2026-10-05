"""Embedded dashboard HTML (single-file, no external deps)."""

INDEX_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAUUSD Pro Bot — Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',Tahoma,sans-serif; background:#0f172a; color:#e2e8f0; min-height:100vh; }
  header { background:#1e293b; padding:1rem 2rem; border-bottom:2px solid #334155; display:flex; justify-content:space-between; align-items:center; }
  header h1 { font-size:1.4rem; color:#fbbf24; }
  .status-pill { padding:.4rem 1rem; border-radius:20px; font-size:.85rem; font-weight:bold; }
  .status-ok { background:#166534; color:#86efac; }
  .status-down { background:#991b1b; color:#fca5a5; }
  .container { max-width:1200px; margin:0 auto; padding:2rem; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin-bottom:2rem; }
  .card { background:#1e293b; border-radius:12px; padding:1.2rem; border:1px solid #334155; }
  .card h3 { font-size:.8rem; color:#94a3b8; text-transform:uppercase; margin-bottom:.5rem; }
  .card .value { font-size:1.8rem; font-weight:bold; color:#fbbf24; }
  .card .sub { font-size:.75rem; color:#64748b; margin-top:.3rem; }
  table { width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; }
  th,td { padding:.8rem; text-align:right; border-bottom:1px solid #334155; font-size:.85rem; }
  th { background:#0f172a; color:#94a3b8; font-weight:600; }
  .buy { color:#4ade80; font-weight:bold; }
  .sell { color:#f87171; font-weight:bold; }
  .section-title { font-size:1.1rem; margin:1.5rem 0 .8rem; color:#cbd5e1; }
  .refresh { text-align:center; margin-top:2rem; color:#64748b; font-size:.75rem; }
  .bar { height:6px; background:#334155; border-radius:3px; overflow:hidden; margin-top:.4rem; }
  .bar-fill { height:100%; background:linear-gradient(90deg,#f59e0b,#fbbf24); }
</style>
</head>
<body>
<header>
  <h1>XAUUSD Pro Signal Bot - Dashboard</h1>
  <span id="statusPill" class="status-pill status-down">Checking...</span>
</header>
<div class="container">
  <div class="grid" id="statsGrid">
    <div class="card"><h3>Signals Today</h3><div class="value" id="sSignals">-</div><div class="sub">Last 24h</div></div>
    <div class="card"><h3>Winning Trades</h3><div class="value buy" id="sWins">-</div><div class="sub">Win rate <span id="sWR">-</span>%</div></div>
    <div class="card"><h3>Net PnL</h3><div class="value" id="sPnl">-</div><div class="sub">USD</div></div>
    <div class="card"><h3>Last Scan</h3><div class="value" id="sScan">-</div><div class="sub">seconds ago</div></div>
  </div>
  <h2 class="section-title">Recent Signals</h2>
  <table>
    <thead><tr><th>ID</th><th>Dir</th><th>Entry</th><th>SL</th><th>TPs</th><th>Confluence</th><th>TF</th><th>Time</th><th>Outcome</th></tr></thead>
    <tbody id="signalsBody"><tr><td colspan="9" style="text-align:center;color:#64748b">Loading...</td></tr></tbody>
  </table>
  <h2 class="section-title">Performance (30d)</h2>
  <div id="perfArea" style="color:#64748b;font-size:.85rem">Loading...</div>
  <div class="refresh">Auto-refresh every 30s</div>
</div>
<script>
async function fetchJSON(url){ try{ const r=await fetch(url); return await r.json(); }catch(e){ return null; } }
async function refresh(){
  const status = await fetchJSON('/api/status');
  const pill = document.getElementById('statusPill');
  if(status && status.running){ pill.textContent='RUNNING'; pill.className='status-pill status-ok'; }
  else { pill.textContent='STOPPED'; pill.className='status-pill status-down'; }
  if(status && status.daily){
    document.getElementById('sSignals').textContent = status.daily.signals_sent||0;
    document.getElementById('sWins').textContent = status.daily.wins||0;
    document.getElementById('sWR').textContent = (status.daily.win_rate||0).toFixed(1);
    document.getElementById('sPnl').textContent = '$'+(status.daily.pnl||0).toFixed(2);
    document.getElementById('sScan').textContent = status.last_scan_age ? Math.round(status.last_scan_age)+'s' : '-';
  }
  const signals = await fetchJSON('/api/signals?limit=15');
  const tbody = document.getElementById('signalsBody');
  if(signals && signals.length){
    tbody.innerHTML = signals.map(s=>'<tr><td><code>'+s.id+'</code></td><td class="'+(s.direction==='BUY'?'buy':'sell')+'">'+(s.direction==='BUY'?'BUY':'SELL')+'</td><td>'+(s.entry||0).toFixed(2)+'</td><td>'+(s.stop_loss||0).toFixed(2)+'</td><td>'+(s.take_profits||'-')+'</td><td><div class="bar"><div class="bar-fill" style="width:'+(s.confluence||0)+'%"></div>'+(s.confluence||0).toFixed(0)+'%</div></td><td>'+s.timeframe+'</td><td>'+(s.created_at||'').slice(0,16).replace('T',' ')+'</td><td>'+(s.outcome||'OPEN')+'</td></tr>').join('');
  } else { tbody.innerHTML='<tr><td colspan="9" style="text-align:center;color:#64748b">No signals yet</td></tr>'; }
  const perf = await fetchJSON('/api/performance?days=30');
  const pa = document.getElementById('perfArea');
  if(perf && perf.length){
    const totalPnl = perf.reduce((a,b)=>a+(b.pnl||0),0);
    const avgWR = perf.reduce((a,b)=>a+(b.win_rate||0),0)/perf.length;
    pa.innerHTML = '<div class="grid"><div class="card"><h3>Total Trades</h3><div class="value">'+perf.reduce((a,b)=>a+(b.trades||0),0)+'</div></div><div class="card"><h3>Avg Win Rate</h3><div class="value">'+avgWR.toFixed(1)+'%</div></div><div class="card"><h3>Total PnL</h3><div class="value">$'+totalPnl.toFixed(2)+'</div></div><div class="card"><h3>Active Days</h3><div class="value">'+perf.length+'</div></div></div>';
  } else { pa.textContent='No performance data yet.'; }
}
refresh(); setInterval(refresh, 30000);
</script>
</body>
</html>
"""
