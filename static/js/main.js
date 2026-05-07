// ─── STATE ────────────────────────────────
let selectedCustomer = 1;
let chatMode = 'general';
let salesData = null;
let mapCustomer = 1;

// ─── INIT ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateTime();
  setInterval(updateTime, 1000);
  buildCustomerButtons();
  checkOllama();
  loadSales();
});

function updateTime() {
  const now = new Date();
  document.getElementById('topbarTime').textContent =
    now.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}

function buildCustomerButtons() {
  const customers = [
    { id: 1,  name: 'Budi Santoso'  },
    { id: 2,  name: 'Siti Rahayu'   },
    { id: 3,  name: 'Agus Permana'  },
    { id: 4,  name: 'Dewi Lestari'  },
    { id: 5,  name: 'Rizky Pratama' },
    { id: 6,  name: 'Rina Wulandari'},
    { id: 7,  name: 'Hendra Wijaya' },
    { id: 8,  name: 'Yanti Kusuma'  },
    { id: 9,  name: 'Doni Setiawan' },
    { id: 10, name: 'Maya Putri'    },
  ];

  const container    = document.getElementById('customerBtns');
  const mapContainer = document.getElementById('mapCustomerBtns');

  customers.forEach(c => {
    // Fraud page button
    const btn = document.createElement('button');
    btn.className = 'cust-btn' + (c.id === 1 ? ' selected' : '');
    btn.textContent = `#${c.id} ${c.name}`;
    btn.onclick = () => selectCustomer(c.id, btn);
    container.appendChild(btn);

    // Map page button
    const mapBtn = document.createElement('button');
    mapBtn.className = 'cust-btn' + (c.id === 1 ? ' selected' : '');
    mapBtn.textContent = `#${c.id} ${c.name}`;
    mapBtn.onclick = () => {
      mapCustomer = c.id;
      loadMap(c.id);
      updateMapBtns(c.id);
    };
    mapContainer.appendChild(mapBtn);
  });
}

function selectCustomer(id, btn) {
  selectedCustomer = id;
  document.querySelectorAll('#customerBtns .cust-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
}

function updateMapBtns(id) {
  document.querySelectorAll('#mapCustomerBtns .cust-btn').forEach((b, i) => {
    b.classList.toggle('selected', i + 1 === id);
  });
}

// ─── PAGE NAVIGATION ───────────────────────
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  document.getElementById(`nav-${page}`).classList.add('active');

  const titles = {
    fraud: ['Fraud Detection — Agentic AI',      '3 agents: Location · Behavior · Conclusion'],
    sales: ['Sales Analytics',                    'Sales dashboard & product stats'],
    map:   ['Transaction Map',                    'Visualisasi lokasi transactions di Indonesia'],
    chat:  ['AI Chat Assistant',                  'Powered by Ollama + Llama3 (local)'],
    log:   ['Fraud Log',                          'Fraud detection history — auto refresh 30s'],
  };

  document.getElementById('pageTitle').textContent    = titles[page][0];
  document.getElementById('pageSubtitle').textContent = titles[page][1];

  if (page === 'map') loadMap(mapCustomer);
  if (page === 'sales') {
    if (salesData) {
      renderSalesPage();
    } else {
      document.getElementById('salesContent').innerHTML =
        '<div class="loading"><div class="spinner"></div> Loading sales data...</div>';
      loadSales().then(() => renderSalesPage());
    }
  }
  if (page === 'log') loadFraudLog();
}

// ─── OLLAMA STATUS CHECK ────────────────────
async function checkOllama() {
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'ping', mode: 'general' }),
    });
    const data = await r.json();
    const ok   = !data.response.includes('⚠️');
    document.getElementById('ollamaIndicator').style.background =
      ok ? 'var(--green)' : 'var(--yellow)';
    document.getElementById('ollamaStatus').textContent = ok ? 'online' : 'offline';
  } catch {
    document.getElementById('ollamaStatus').textContent = 'error';
  }
}

// ─── FRAUD ANALYSIS ────────────────────────
async function runFraudAnalysis() {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled    = true;
  btn.textContent = '⏳ Analyzing...';

  document.getElementById('fraudResult').style.display  = 'none';
  document.getElementById('fraudLoading').style.display = 'block';
  document.getElementById('analyzeInfo').textContent    = '';

  try {
    const [fraud, txns] = await Promise.all([
      fetch(`/api/fraud/${selectedCustomer}`).then(r => r.json()),
      fetch(`/api/transactions/${selectedCustomer}`).then(r => r.json()),
    ]);

    renderFraudResult(fraud, txns);
    document.getElementById('fraudLoading').style.display = 'none';
    document.getElementById('fraudResult').style.display  = 'block';
    document.getElementById('analyzeInfo').textContent    =
      `Analysis complete for Customer #${selectedCustomer}`;
  } catch (e) {
    document.getElementById('fraudLoading').innerHTML =
      `<div style="padding:20px;color:var(--red)">Error: ${e.message}</div>`;
  }

  btn.disabled    = false;
  btn.textContent = '⚡ Jalankan Analisis';
}

function renderFraudResult(data, txns) {
  const a1 = data.agent1;
  const a2 = data.agent2;
  const a3 = data.agent3;
  const d  = a2.details;

  // ── Agent cards ──
  setAgentCard('1', a1.status, a1.score, a1.reason);
  setAgentCard('2', a2.status, a2.score,
    `${d.total_transactions} transactions | avg Rp${fmt(d.average_amount)}`);
  setAgentCard('3', a3.final_status, a3.combined_score,
    `Combined: ${a3.combined_score}/100`);

  // ── Verdict banner ──
  const vc = document.getElementById('verdictCard');
  vc.className = `verdict-card verdict-${a3.final_status.toLowerCase()}`;
  document.getElementById('verdictAction').textContent = a3.action;
  document.getElementById('verdictRec').textContent    = a3.recommendation;

  // ── Behaviour detail list ──
  document.getElementById('behaviourDetails').innerHTML = `
    <div class="detail-row">
      <span class="detail-key">Total Transactions (3 mo)</span>
      <span class="detail-val">${d.total_transactions}x</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">Average</span>
      <span class="detail-val">Rp ${fmt(d.average_amount)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">Highest</span>
      <span class="detail-val">Rp ${fmt(d.max_amount)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">Lowest</span>
      <span class="detail-val">Rp ${fmt(d.min_amount)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">Unique cities</span>
      <span class="detail-val">${d.unique_cities} cities</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">This week</span>
      <span class="detail-val">${d.recent_week_count}x transactions</span>
    </div>
    <div class="detail-row">
      <span class="detail-key">High-Risk Merchants</span>
      <span class="detail-val" style="color: ${d.risky_merchant_count > 0 ? 'var(--red)' : ''}">
        ${d.risky_merchant_count} transactions
      </span>
    </div>
    ${(d.alerts || []).map(a => `<div class="alert-item">⚠️ ${a}</div>`).join('')}
  `;

  // Helper for risk badge
  const getRiskBadge = (category, level) => {
    if (!category) return '<span style="color:var(--muted)">Normal</span>';
    const cls = level === 'high' ? 'merchant-risk-high' :
                level === 'medium' ? 'merchant-risk-medium' :
                'merchant-risk-low';
    return `<span class="flag-pill ${cls}">${category}</span>`;
  };

  // ── Transaction table ──
  document.getElementById('txnTableBody').innerHTML = txns.slice(0, 10).map(t => {
    // Get merchant info if it was analyzed in Agent 1
    const a1Match = (a1.details || []).find(p => p.txn_current.id === t.id);
    const cat = a1Match?.txn_current.merchant_risk_label || null;
    const lvl = a1Match?.txn_current.merchant_risk_level || null;
    return `
    <tr>
      <td style="font-family:var(--mono);font-size:11px">${t.timestamp.slice(0, 16)}</td>
      <td>${t.merchant}</td>
      <td>${getRiskBadge(cat, lvl)}</td>
      <td>${t.city}</td>
      <td style="font-family:var(--mono)">Rp ${fmt(t.amount)}</td>
      <td><span class="flag-pill ${t.flagged ? 'flagged' : 'normal'}">${t.flagged ? 'FLAG' : 'OK'}</span></td>
    </tr>
  `}).join('');

  // ── Suspicious pairs (Agent 1) ──
  const suspPairs = (a1.details || []).filter(p => p.is_suspicious);
  const spEl = document.getElementById('suspiciousPairs');

  if (suspPairs.length === 0) {
    spEl.innerHTML =
      '<div style="color:var(--green);font-size:13px;padding:12px">✓ Tidak ada pasangan transactions mencurigakan</div>';
  } else {
    spEl.innerHTML = suspPairs.map(p => `
      <div style="background:rgba(239,68,68,0.07);border:1px solid rgba(239,68,68,0.2);border-radius:8px;padding:14px;margin-bottom:10px">
        <div style="display:flex;gap:24px;flex-wrap:wrap;font-size:13px">
          <div>
            <span style="color:var(--muted);font-family:var(--mono);font-size:11px">FROM</span><br>
            <strong>${p.txn_previous.city}</strong> — ${p.txn_previous.time.slice(0, 16)}<br>
            <span style="color:var(--muted)">Rp ${fmt(p.txn_previous.amount)}</span>
          </div>
          <div style="display:flex;align-items:center;color:var(--red)">→</div>
          <div>
            <span style="color:var(--muted);font-family:var(--mono);font-size:11px">TO</span><br>
            <strong>${p.txn_current.city}</strong> — ${p.txn_current.time.slice(0, 16)}<br>
            <span style="color:var(--muted)">Rp ${fmt(p.txn_current.amount)}</span>
            ${p.txn_current.merchant_risk_label ? `<div style="margin-top:4px"><span class="flag-pill merchant-risk-${p.txn_current.merchant_risk_level}">${p.txn_current.merchant_risk_label}</span></div>` : ''}
          </div>
          <div style="margin-left:auto;text-align:right">
            <div style="color:var(--red);font-weight:700;font-family:var(--mono)">${p.distance_km} km</div>
            <div style="font-size:12px;color:var(--muted)">Delay: ${p.time_diff_hours}h</div>
            <div style="font-size:12px;color:var(--muted)">Min travel time: ${p.min_travel_hours}h</div>
          </div>
        </div>
      </div>
    `).join('');
  }
}

function setAgentCard(num, status, score, detail) {
  const s       = status.toLowerCase();
  const badgeCls = s === 'fraud' ? 'badge-fraud' : s === 'warning' ? 'badge-warning' : 'badge-safe';
  const fillCls  = s === 'fraud' ? 'fill-fraud'  : s === 'warning' ? 'fill-warning'  : 'fill-safe';

  document.getElementById(`a${num}badge`).textContent = status;
  document.getElementById(`a${num}badge`).className   = `status-badge ${badgeCls}`;
  document.getElementById(`a${num}score`).textContent = score;
  document.getElementById(`a${num}bar`).style.width   = `${score}%`;
  document.getElementById(`a${num}bar`).className     = `score-fill ${fillCls}`;
  document.getElementById(`a${num}detail`).textContent = detail;
}

// ─── SALES ─────────────────────────────────
async function loadSales() {
  try {
    salesData = await fetch('/api/sales/summary').then(r => r.json());
  } catch (e) {
    console.error('Failed to load sales data:', e);
  }
}

function renderSalesPage() {
  if (!salesData) return;
  const s = salesData;

  document.getElementById('salesContent').innerHTML = `
    <div class="grid-4" style="margin-bottom:20px">
      <div class="stat-card">
        <div class="stat-label">Total Revenue</div>
        <div class="stat-value" style="font-size:20px">Rp ${fmtBig(s.total_revenue)}</div>
        <div class="stat-sub">last 6 months</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Transactions</div>
        <div class="stat-value">${s.total_transactions}</div>
        <div class="stat-sub">orders</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Transactions</div>
        <div class="stat-value" style="font-size:20px">Rp ${fmtBig(s.avg_transaction)}</div>
        <div class="stat-sub">per order</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Top Category</div>
        <div class="stat-value" style="font-size:18px">${s.by_category[0]?.category || '—'}</div>
        <div class="stat-sub">Rp ${fmtBig(s.by_category[0]?.revenue || 0)}</div>
      </div>
    </div>

    <div class="grid-2" style="margin-bottom:20px">
      <div class="card">
        <div class="card-title">Monthly Revenue Trend</div>
        <div class="chart-wrap"><canvas id="monthlyChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title">Revenue per Category</div>
        <div class="chart-wrap"><canvas id="catChart"></canvas></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">Revenue per Region</div>
        <div class="chart-wrap"><canvas id="regionChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title">Top 10 Products</div>
        <div style="overflow-y:auto;max-height:250px">
          <table class="txn-table">
            <thead>
              <tr><th>#</th><th>Product</th><th>Category</th><th>Revenue</th></tr>
            </thead>
            <tbody>
              ${s.top_products.map((p, i) => `
                <tr>
                  <td style="color:var(--muted);font-family:var(--mono)">${i + 1}</td>
                  <td>${p.product}</td>
                  <td>
                    <span style="font-size:11px;padding:2px 8px;border-radius:4px;
                      background:rgba(0,212,255,0.1);color:var(--accent)">
                      ${p.category}
                    </span>
                  </td>
                  <td style="font-family:var(--mono)">Rp ${fmtBig(p.revenue)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  // Render charts after DOM is ready
  setTimeout(() => renderSalesCharts(s), 100);
}

function renderSalesCharts(s) {
  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans' } } },
    },
  };
  const gridOpts = { color: 'rgba(30,45,69,0.8)' };
  const tickOpts = { color: '#64748b' };

  // Monthly trend line chart
  new Chart(document.getElementById('monthlyChart'), {
    type: 'line',
    data: {
      labels: s.monthly_trend.map(m => m.month),
      datasets: [{
        label: 'Revenue',
        data: s.monthly_trend.map(m => m.revenue),
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0,212,255,0.08)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#00d4ff',
      }],
    },
    options: {
      ...chartDefaults,
      scales: {
        x: { grid: gridOpts, ticks: tickOpts },
        y: { grid: gridOpts, ticks: { ...tickOpts, callback: v => 'Rp ' + fmtBig(v) } },
      },
    },
  });

  // Category doughnut chart
  new Chart(document.getElementById('catChart'), {
    type: 'doughnut',
    data: {
      labels: s.by_category.map(c => c.category),
      datasets: [{
        data: s.by_category.map(c => c.revenue),
        backgroundColor: ['#00d4ff', '#7c3aed', '#10b981'],
        borderColor: '#111827',
        borderWidth: 3,
      }],
    },
    options: { ...chartDefaults },
  });

  // Region bar chart
  new Chart(document.getElementById('regionChart'), {
    type: 'bar',
    data: {
      labels: s.by_region.map(r => r.region),
      datasets: [{
        label: 'Revenue',
        data: s.by_region.map(r => r.revenue),
        backgroundColor: 'rgba(124,58,237,0.7)',
        borderColor: '#7c3aed',
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      ...chartDefaults,
      scales: {
        x: { grid: gridOpts, ticks: tickOpts },
        y: { grid: gridOpts, ticks: { ...tickOpts, callback: v => 'Rp ' + fmtBig(v) } },
      },
    },
  });
}

// ─── MAP ────────────────────────────────────
async function loadMap(custId) {
  const txns   = await fetch(`/api/transactions/${custId}`).then(r => r.json());
  const canvas = document.getElementById('indonesiaMap');
  const ctx    = canvas.getContext('2d');

  canvas.width  = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  const W = canvas.width;
  const H = canvas.height;

  // Indonesia bounding box
  const minLon = 95, maxLon = 141, minLat = -11, maxLat = 6;
  const toX = lon => ((lon - minLon) / (maxLon - minLon)) * (W - 80) + 40;
  const toY = lat => ((maxLat - lat) / (maxLat - minLat)) * (H - 80) + 40;

  // Background
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#0d1520';
  ctx.fillRect(0, 0, W, H);

  // Grid
  ctx.strokeStyle = 'rgba(0,212,255,0.04)';
  ctx.lineWidth   = 1;
  for (let x = 0; x < W; x += 40) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 0; y < H; y += 40) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }

  // Group transactions by city
  const cityMap = {};
  txns.forEach(t => {
    if (!cityMap[t.city]) {
      cityMap[t.city] = { lat: t.lat, lon: t.lon, count: 0, flagged: 0, amounts: [] };
    }
    cityMap[t.city].count++;
    if (t.flagged) cityMap[t.city].flagged++;
    cityMap[t.city].amounts.push(t.amount);
  });

  // Draw flagged connection line
  const flagged = txns.filter(t => t.flagged);
  if (flagged.length >= 2) {
    ctx.beginPath();
    ctx.moveTo(toX(flagged[0].lon), toY(flagged[0].lat));
    ctx.lineTo(toX(flagged[1].lon), toY(flagged[1].lat));
    ctx.strokeStyle = 'rgba(239,68,68,0.5)';
    ctx.lineWidth   = 2;
    ctx.setLineDash([6, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Draw normal transaction connections
  const normal = txns.filter(t => !t.flagged).slice(0, 5);
  for (let i = 0; i < normal.length - 1; i++) {
    ctx.beginPath();
    ctx.moveTo(toX(normal[i].lon),     toY(normal[i].lat));
    ctx.lineTo(toX(normal[i+1].lon),   toY(normal[i+1].lat));
    ctx.strokeStyle = 'rgba(0,212,255,0.12)';
    ctx.lineWidth   = 1;
    ctx.stroke();
  }

  // Draw city nodes
  Object.entries(cityMap).forEach(([name, data]) => {
    const x     = toX(data.lon);
    const y     = toY(data.lat);
    const r     = Math.min(4 + data.count * 1.5, 18);
    const color = data.flagged > 0 ? '#ef4444' : '#00d4ff';

    // Glow effect
    const grd = ctx.createRadialGradient(x, y, 0, x, y, r * 2.5);
    grd.addColorStop(0, color + '33');
    grd.addColorStop(1, 'transparent');
    ctx.beginPath();
    ctx.arc(x, y, r * 2.5, 0, Math.PI * 2);
    ctx.fillStyle = grd;
    ctx.fill();

    // Outer circle
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle   = color + '22';
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5;
    ctx.fill();
    ctx.stroke();

    // Center dot
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // City label
    ctx.fillStyle = '#e2e8f0';
    ctx.font      = '11px DM Sans';
    ctx.fillText(name, x + r + 4, y + 4);

    // Transaction count
    if (data.count > 1) {
      ctx.fillStyle = color + 'aa';
      ctx.font      = 'bold 10px Space Mono';
      ctx.fillText(`×${data.count}`, x + r + 4, y + 16);
    }
  });

  // Update legend
  document.getElementById('mapLegend').innerHTML = `
    <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)">
      <div style="width:10px;height:10px;border-radius:50%;background:#00d4ff"></div>
      Transactions normal
    </div>
    <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)">
      <div style="width:10px;height:10px;border-radius:50%;background:#ef4444"></div>
      Transactions mencurigakan
    </div>
    <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)">
      <div style="width:20px;height:2px;background:#ef4444;border-top:1px dashed #ef4444"></div>
      Suspicious distance
    </div>
    <div style="color:var(--muted);font-size:12px;margin-left:auto">
      Customer #${custId} | ${txns.length} transactions
    </div>
  `;
}

// ─── CHAT ───────────────────────────────────
function setChatMode(mode) {
  chatMode = mode;
  document.querySelectorAll('.mode-tab').forEach((t, i) => {
    t.classList.toggle('active', ['general', 'fraud', 'sales'][i] === mode);
  });
  document.getElementById('fraudCustSelect').style.display =
    mode === 'fraud' ? 'flex' : 'none';
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg   = input.value.trim();
  if (!msg) return;

  addMsg(msg, 'user');
  input.value = '';

  const btn         = document.getElementById('sendBtn');
  btn.disabled      = true;
  const thinkingId  = 'thinking-' + Date.now();
  addMsg('⏳ Processing...', 'ai', thinkingId);

  try {
    const body = { message: msg, mode: chatMode };
    if (chatMode === 'fraud') {
      body.context_id = parseInt(document.getElementById('chatCustSelect').value);
    }

    const r    = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    document.getElementById(thinkingId)?.remove();
    addMsg(data.response, 'ai');
  } catch (e) {
    document.getElementById(thinkingId)?.remove();
    addMsg('Error: ' + e.message, 'ai');
  }

  btn.disabled = false;
}

function addMsg(text, role, id) {
  const container = document.getElementById('chatMessages');
  const div       = document.createElement('div');
  div.className   = `msg ${role}`;
  if (id) div.id  = id;
  div.innerHTML   = `
    <div class="msg-avatar">${role === 'user' ? '👤' : '🤖'}</div>
    <div class="msg-bubble">${text.replace(/\n/g, '<br>')}</div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ─── UTILITY FORMATTERS ─────────────────────
function fmt(n) {
  return Math.round(n).toLocaleString('id-ID');
}

function fmtBig(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'M';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'jt';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'rb';
  return Math.round(n).toString();
}

// Render sales page once data is ready (in case user lands on sales tab)
setTimeout(() => { if (salesData) renderSalesPage(); }, 1000);

// ─── CSV UPLOAD ─────────────────────────────
async function handleCsvUpload(input) {
  const file = input.files[0];
  if (!file) return;

  // Reset input so same file can be uploaded again
  input.value = '';

  // Show uploading state
  showCsvNotification('⏳ Uploading and validating CSV...', 'partial');

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/upload/transactions', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      showCsvNotification(`❌ Upload failed: ${err.detail || 'Unknown error'}`, 'error');
      return;
    }

    const result = await response.json();
    const { success_count, failed_count, total_rows, errors, customers_affected } = result;

    if (success_count === 0 && failed_count > 0) {
      // All failed
      const errorList = errors.slice(0, 5).join('<br>');
      showCsvNotification(
        `❌ Failed to import ${failed_count} dari ${total_rows} baris.<br>` +
        `<div style="margin-top:6px;font-size:12px;opacity:0.8">${errorList}</div>`,
        'error'
      );
    } else if (failed_count > 0) {
      // Partial success
      const errorList = errors.slice(0, 3).join('<br>');
      showCsvNotification(
        `⚠️ ${success_count} transactions berhasil diimport, ${failed_count} rows ignored.<br>` +
        `Affected customers: ${customers_affected.map(id => '#' + id).join(', ')}<br>` +
        `<div style="margin-top:6px;font-size:12px;opacity:0.8">${errorList}</div>`,
        'partial'
      );
    } else {
      // All success
      showCsvNotification(
        `✅ Successfully imported ${success_count} transactions from file "${file.name}".<br>` +
        `Affected customers: ${customers_affected.map(id => '#' + id).join(', ')}`,
        'success'
      );
    }
  } catch (e) {
    showCsvNotification(`❌ Error: ${e.message}`, 'error');
  }
}

function showCsvNotification(html, type) {
  const el = document.getElementById('csvNotification');
  el.innerHTML   = html;
  el.className   = `csv-notification ${type}`;
  el.style.display = 'block';

  // Auto-hide after 10 seconds (except errors)
  if (type !== 'error') {
    setTimeout(() => { el.style.display = 'none'; }, 10000);
  }
}

// ─── FRAUD LOG ───────────────────────────────
let logRefreshTimer = null;

async function loadFraudLog() {
  const container = document.getElementById('logContent');
  if (!container) return;

  try {
    const logs = await fetch('/api/fraud-log').then(r => r.json());
    renderFraudLog(logs);
  } catch (e) {
    container.innerHTML = `<div style="color:var(--red);padding:20px">Error: ${e.message}</div>`;
  }

  // Auto refresh tiap 30 detik
  clearInterval(logRefreshTimer);
  logRefreshTimer = setInterval(async () => {
    const logs = await fetch('/api/fraud-log').then(r => r.json());
    renderFraudLog(logs);
    document.getElementById('logLastUpdate').textContent =
      'Last update: ' + new Date().toLocaleTimeString('id-ID');
  }, 30000);
}

function renderFraudLog(logs) {
  const container = document.getElementById('logContent');
  if (!container) return;

  // Stats summary
  const total   = logs.length;
  const fraud   = logs.filter(l => l.verdict === 'FRAUD').length;
  const warning = logs.filter(l => l.verdict === 'WARNING').length;
  const aman    = logs.filter(l => l.verdict === 'SAFE').length;

  // Filter state
  const activeFilter = document.getElementById('logFilter')?.value || 'ALL';
  const filtered = activeFilter === 'ALL' ? logs : logs.filter(l => l.verdict === activeFilter);

  container.innerHTML = `
    <!-- Summary stats -->
    <div class="grid-4" style="margin-bottom:20px">
      <div class="stat-card">
        <div class="stat-label">Total Checks</div>
        <div class="stat-value">${total}</div>
        <div class="stat-sub">all analyses</div>
      </div>
      <div class="stat-card" style="border-top-color:var(--red)">
        <div class="stat-label">FRAUD</div>
        <div class="stat-value" style="color:var(--red)">${fraud}</div>
        <div class="stat-sub">detected</div>
      </div>
      <div class="stat-card" style="border-top-color:var(--yellow)">
        <div class="stat-label">WARNING</div>
        <div class="stat-value" style="color:var(--yellow)">${warning}</div>
        <div class="stat-sub">needs verification</div>
      </div>
      <div class="stat-card" style="border-top-color:var(--green)">
        <div class="stat-label">AMAN</div>
        <div class="stat-value" style="color:var(--green)">${safe}</div>
        <div class="stat-sub">transactions normal</div>
      </div>
    </div>

    <!-- Filter & refresh info -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;gap:8px">
        <select id="logFilter" onchange="applyLogFilter(this.value)"
          style="background:var(--surface);border:1px solid var(--border);border-radius:6px;
                 padding:6px 12px;color:var(--text);font-size:13px;cursor:pointer">
          <option value="ALL"     ${activeFilter==='ALL'     ? 'selected':''}>All</option>
          <option value="FRAUD"   ${activeFilter==='FRAUD'   ? 'selected':''}>🔴 FRAUD</option>
          <option value="WARNING" ${activeFilter==='WARNING' ? 'selected':''}>🟡 WARNING</option>
          <option value="AMAN"    ${activeFilter==='SAFE'    ? 'selected':''}>🟢 SAFE</option>
        </select>
        <button onclick="loadFraudLog()" class="analyze-btn" style="padding:6px 16px;font-size:13px">
          🔄 Refresh
        </button>
      </div>
      <span id="logLastUpdate" style="font-size:12px;color:var(--muted);font-family:var(--mono)">
        Auto refresh: 30 seconds
      </span>
    </div>

    <!-- Log table -->
    <div class="card">
      <div style="overflow-x:auto">
        <table class="txn-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Nasabah</th>
              <th>Verdict</th>
              <th>Score</th>
              <th>Agent 1</th>
              <th>Agent 2</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${filtered.length === 0
              ? `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:32px">
                   No logs yet. Run an N8N workflow or click Refresh.
                 </td></tr>`
              : filtered.map(l => `
                <tr>
                  <td style="font-family:var(--mono);font-size:11px">${l.timestamp}</td>
                  <td>
                    <div style="font-weight:600">${l.customer || 'Customer #' + l.customer_id}</div>
                    <div style="font-size:11px;color:var(--muted)">ID: ${l.customer_id}</div>
                  </td>
                  <td>
                    <span class="status-badge badge-${l.verdict.toLowerCase()}">
                      ${l.verdict}
                    </span>
                  </td>
                  <td>
                    <div style="font-family:var(--mono);font-weight:700;
                      color:${l.verdict==='FRAUD'?'var(--red)':l.verdict==='WARNING'?'var(--yellow)':'var(--green)'}">
                      ${l.score}/100
                    </div>
                    <div class="score-bar" style="margin-top:4px;width:80px">
                      <div class="score-fill fill-${l.verdict.toLowerCase()}"
                           style="width:${l.score}%"></div>
                    </div>
                  </td>
                  <td style="font-family:var(--mono);font-size:12px">${l.agent1_score ?? '—'}</td>
                  <td style="font-family:var(--mono);font-size:12px">${l.agent2_score ?? '—'}</td>
                  <td style="font-size:12px">${l.action || '—'}</td>
                </tr>
              `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function applyLogFilter(verdict) {
  fetch('/api/fraud-log')
    .then(r => r.json())
    .then(logs => {
      const filtered = verdict === 'ALL' ? logs : logs.filter(l => l.verdict === verdict);
      renderFraudLog(filtered.length ? filtered : logs);
      // Re-set filter value
      const sel = document.getElementById('logFilter');
      if (sel) sel.value = verdict;
    });
}