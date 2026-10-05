// Dashboard JavaScript — live data fetching & rendering
async function fetchJSON(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) { return null; }
}

function fmt(n, d=2) { return (n||0).toFixed(d); }
function fmtUsd(n) { return '$' + (n||0).toFixed(2); }

async function refreshStatus() {
  const s = await fetchJSON('/api/status');
  const pill = document.getElementById('statusPill');
  if (s && s.running) { pill.textContent='● RUNNING'; pill.className='status-pill status-ok'; }
  else { pill.textContent='● STOPPED'; pill.className='status-pill status-down'; }
  if (s && s.daily) {
    document.getElementById('sSignals').textContent = s.daily.signals_sent||0;
    document.getElementById('sWins').textContent = s.daily.wins||0;
    document.getElementById('sWR').textContent = fmt(s.daily.win_rate,1);
    document.getElementById('sPnl').textContent = fmtUsd(s.daily.pnl);
    document.getElementById('sScan').textContent = s.last_scan_age ? Math.round(s.last_scan_age)+'s' : '-';
  }
}

async function refreshSignals() {
  const sigs = await fetchJSON('/api/signals?limit=15');
  const tbody = document.getElementById('signalsBody');
  if (!sigs || !sigs.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#64748b">No signals yet</td></tr>';
    return;
  }
  tbody.innerHTML = sigs.map(s => {
    const dir = s.direction==='BUY' ? '<span class="buy">BUY</span>' : '<span class="sell">SELL</span>';
    const conf = s.confluence||0;
    return `<tr>
      <td><code>${s.id}</code></td><td>${dir}</td>
      <td>${fmt(s.entry)}</td><td>${fmt(s.stop_loss)}</td><td>${s.take_profits||'-'}</td>
      <td><div class="bar"><div class="bar-fill" style="width:${conf}%"></div>${conf.toFixed(0)}%</div></td>
      <td>${s.timeframe}</td><td>${(s.created_at||'').slice(0,16).replace('T',' ')}</td>
      <td>${s.outcome||'OPEN'}</td></tr>`;
  }).join('');
}

async function refreshPerformance() {
  const perf = await fetchJSON('/api/performance?days=30');
  const pa = document.getElementById('perfArea');
  if (!perf || !perf.length) { pa.textContent='No performance data yet.'; return; }
  const totalPnl = perf.reduce((a,b)=>a+(b.pnl||0),0);
  const avgWR = perf.reduce((a,b)=>a+(b.win_rate||0),0)/perf.length;
  const totalTrades = perf.reduce((a,b)=>a+(b.trades||0),0);
  pa.innerHTML = `<div class="grid">
    <div class="card"><h3>Total Trades</h3><div class="value">${totalTrades}</div></div>
    <div class="card"><h3>Avg Win Rate</h3><div class="value">${fmt(avgWR,1)}%</div></div>
    <div class="card"><h3>Total PnL</h3><div class="value">${fmtUsd(totalPnl)}</div></div>
    <div class="card"><h3>Active Days</h3><div class="value">${perf.length}</div></div>
  </div>`;
}

async function refreshOpenTrades() {
  const trades = await fetchJSON('/api/trades/open');
  const el = document.getElementById('openTrades');
  if (!trades || !trades.length) { el.innerHTML = '<p style="color:#64748b">No open trades.</p>'; return; }
  el.innerHTML = '<table><thead><tr><th>ID</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP</th><th>Lot</th></tr></thead><tbody>' +
    trades.map(t=>`<tr><td><code>${t.signal_id}</code></td>
      <td class="${t.direction==='BUY'?'buy':'sell'}">${t.direction}</td>
      <td>${fmt(t.entry)}</td><td>${fmt(t.sl)}</td><td>${fmt(t.tp)}</td><td>${t.lot}</td></tr>`).join('') +
    '</tbody></table>';
}

async function refreshAll() {
  await Promise.all([refreshStatus(), refreshSignals(), refreshPerformance(), refreshOpenTrades()]);
}

refreshAll();
setInterval(refreshAll, 30000);
