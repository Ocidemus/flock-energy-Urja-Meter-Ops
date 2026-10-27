from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Web UI"])

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flock Energy — Urja Meter Ops</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen">
  <!-- Top Navigation -->
  <header class="bg-slate-900 text-white shadow">
    <div class="max-w-7xl mx-auto px-4 py-4 flex flex-wrap justify-between items-center gap-4">
      <div class="flex items-center gap-3">
        <div class="h-9 w-9 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-white shadow-sm">
          ⚡
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight">Urja Meter Ops API</h1>
          <p class="text-xs text-slate-400">Distribution Utility Operations & Telemetry Explorer</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-xs">
        <span id="health-badge" class="px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></span> Connecting...
        </span>
        <a href="/docs" target="_blank" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-md font-medium text-slate-200 transition">Interactive Docs (Swagger)</a>
        <a href="/openapi.json" target="_blank" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-md font-medium text-slate-200 transition">openapi.json</a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">
    <!-- Stat Summary Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Meters</p>
        <p id="stat-meters" class="text-2xl font-bold text-slate-900 mt-1">403</p>
        <p class="text-xs text-emerald-600 mt-1 font-medium">100% telemetry synced</p>
      </div>
      <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Transformers (DTs)</p>
        <p id="stat-dts" class="text-2xl font-bold text-slate-900 mt-1">40</p>
        <p class="text-xs text-slate-500 mt-1">Across 28 feeders</p>
      </div>
      <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Active Faults</p>
        <p id="stat-faults" class="text-2xl font-bold text-amber-600 mt-1">--</p>
        <p class="text-xs text-slate-500 mt-1">Flagged for field service</p>
      </div>
      <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <p class="text-xs font-medium text-slate-500 uppercase tracking-wider">Hierarchy Depth</p>
        <p class="text-2xl font-bold text-slate-900 mt-1">7 Levels</p>
        <p class="text-xs text-slate-500 mt-1">Zone to Consumer</p>
      </div>
    </div>

    <!-- Main Content Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left Column: Search & Meter List (7 cols) -->
      <div class="lg:col-span-7 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 space-y-3">
          <div class="flex justify-between items-center">
            <h2 class="text-base font-semibold text-slate-900">Meter Directory</h2>
            <span id="meters-count-badge" class="text-xs text-slate-500 font-medium">Loading meters...</span>
          </div>
          
          <!-- Filters Row -->
          <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <div class="sm:col-span-2">
              <input id="search-input" type="text" placeholder="Search by meter ID or serial..." 
                     class="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-500" />
            </div>
            <div>
              <select id="filter-status" class="w-full text-xs px-2.5 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-500 bg-white">
                <option value="">All Statuses</option>
                <option value="Installed">Installed</option>
                <option value="Faulty">Faulty</option>
                <option value="Decommissioned">Decommissioned</option>
              </select>
            </div>
            <div>
              <select id="filter-make" class="w-full text-xs px-2.5 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-500 bg-white">
                <option value="">All Makes</option>
                <option value="Genus">Genus</option>
                <option value="HPL">HPL</option>
                <option value="L&T">L&T</option>
                <option value="Secure">Secure</option>
                <option value="Allied">Allied</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Table Container -->
        <div class="overflow-x-auto flex-1">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 text-slate-500 font-medium border-b border-slate-200 uppercase tracking-wider">
              <tr>
                <th class="px-4 py-2.5">Meter ID</th>
                <th class="px-4 py-2.5">Serial</th>
                <th class="px-4 py-2.5">Make</th>
                <th class="px-4 py-2.5">Phase</th>
                <th class="px-4 py-2.5">Status</th>
                <th class="px-4 py-2.5">DT</th>
              </tr>
            </thead>
            <tbody id="meters-table-body" class="divide-y divide-slate-100">
              <tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">Loading meter records...</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination Bar -->
        <div class="p-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 bg-slate-50/50 rounded-b-xl">
          <button id="btn-prev" class="px-3 py-1 rounded border border-slate-300 hover:bg-white disabled:opacity-40">Previous</button>
          <span id="page-label">Page 1 of 1</span>
          <button id="btn-next" class="px-3 py-1 rounded border border-slate-300 hover:bg-white disabled:opacity-40">Next</button>
        </div>
      </div>

      <!-- Right Column: Detail & Consumption Panel (5 cols) -->
      <div class="lg:col-span-5 space-y-6">
        <!-- Meter Details Card -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div class="flex justify-between items-start mb-4">
            <div>
              <span id="detail-badge" class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600">Selected Meter</span>
              <h3 id="detail-id" class="text-xl font-bold text-slate-900 mt-1">Select a meter</h3>
              <p id="detail-serial" class="text-xs text-slate-400">Click any meter row to inspect full profile & telemetry</p>
            </div>
            <div id="detail-status-pill" class="hidden"></div>
          </div>

          <div id="detail-content" class="hidden space-y-4">
            <!-- Specs Grid -->
            <div class="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded-lg border border-slate-100">
              <div><span class="text-slate-400">Make:</span> <strong id="spec-make" class="text-slate-700"></strong></div>
              <div><span class="text-slate-400">Phase:</span> <strong id="spec-phase" class="text-slate-700"></strong></div>
              <div><span class="text-slate-400">Type:</span> <strong id="spec-type" class="text-slate-700"></strong></div>
              <div><span class="text-slate-400">Build:</span> <strong id="spec-build" class="text-slate-700"></strong></div>
              <div><span class="text-slate-400">DT Code:</span> <strong id="spec-dt" class="text-slate-700"></strong></div>
              <div><span class="text-slate-400">Coordinates:</span> <strong id="spec-geo" class="text-slate-700"></strong></div>
            </div>

            <!-- Hierarchy Breadcrumbs -->
            <div>
              <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Network Hierarchy</h4>
              <div id="hierarchy-breadcrumbs" class="text-xs text-slate-600 flex flex-wrap gap-1 items-center bg-slate-50 p-2.5 rounded-lg border border-slate-100"></div>
            </div>

            <!-- Consumption Chart -->
            <div>
              <div class="flex justify-between items-center mb-2">
                <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Interval Consumption (kWh)</h4>
                <span id="consumption-stats" class="text-[11px] text-slate-400">30-min intervals</span>
              </div>
              <div class="h-48 w-full bg-slate-50 p-2 rounded-lg border border-slate-100 relative">
                <canvas id="consumptionChart"></canvas>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick API Guide Card -->
        <div class="bg-slate-900 text-slate-300 rounded-xl shadow-sm p-4 text-xs space-y-2">
          <p class="font-semibold text-white">Programmatic API Endpoints:</p>
          <ul class="space-y-1 font-mono text-[11px] text-emerald-400">
            <li>GET /api/v1/meters?q=J100&status=Installed</li>
            <li>GET /api/v1/meters/{id}</li>
            <li>GET /api/v1/meters/{id}/consumption?from=2026-06-25</li>
            <li>GET /api/v1/transformers</li>
            <li>GET /api/v1/network/hierarchy</li>
            <li>GET /api/v1/export/meters</li>
          </ul>
        </div>
      </div>
    </div>
  </main>

  <script>
    let state = {
      page: 1,
      totalPages: 1,
      selectedMeterId: null,
      chartInstance: null
    };

    async function loadHealth() {
      try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        const badge = document.getElementById('health-badge');
        if (data.status === 'healthy') {
          badge.className = 'px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1.5';
          badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span> Synced (' + data.cached_meters + ' meters)';
        }
      } catch (err) {
        console.error('Health check failed', err);
      }
    }

    async function fetchMeters() {
      const q = document.getElementById('search-input').value;
      const status = document.getElementById('filter-status').value;
      const make = document.getElementById('filter-make').value;
      
      const params = new URLSearchParams({ page: state.page, page_size: 15 });
      if (q) params.set('q', q);
      if (status) params.set('status', status);
      if (make) params.set('make', make);

      const res = await fetch('/api/v1/meters?' + params);
      const json = await res.json();
      
      state.totalPages = json.total_pages;
      document.getElementById('page-label').textContent = 'Page ' + json.page + ' of ' + json.total_pages;
      document.getElementById('meters-count-badge').textContent = json.total + ' total meters';
      document.getElementById('btn-prev').disabled = json.page <= 1;
      document.getElementById('btn-next').disabled = json.page >= json.total_pages;

      renderMetersTable(json.data);
      if (json.data.length > 0 && !state.selectedMeterId) {
        selectMeter(json.data[0].meter_id);
      }
    }

    function renderMetersTable(meters) {
      const tbody = document.getElementById('meters-table-body');
      if (!meters || meters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">No meters matched criteria.</td></tr>';
        return;
      }

      tbody.innerHTML = meters.map(m => {
        const statusColors = {
          'Installed': 'bg-emerald-50 text-emerald-700 border-emerald-200',
          'Faulty': 'bg-amber-50 text-amber-700 border-amber-200',
          'Decommissioned': 'bg-slate-100 text-slate-600 border-slate-200'
        };
        const badgeClass = statusColors[m.install_status] || 'bg-slate-100 text-slate-600';
        const isSelected = m.meter_id === state.selectedMeterId ? 'bg-blue-50/70 font-semibold' : 'hover:bg-slate-50';

        return `<tr class="cursor-pointer transition ${isSelected}" onclick="selectMeter('${m.meter_id}')">
          <td class="px-4 py-2.5 font-medium text-blue-600">${m.meter_id}</td>
          <td class="px-4 py-2.5 text-slate-600 font-mono text-[11px]">${m.serial_number}</td>
          <td class="px-4 py-2.5 text-slate-700">${m.make}</td>
          <td class="px-4 py-2.5 text-slate-600 capitalize">${m.phase_type}</td>
          <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] border ${badgeClass}">${m.install_status}</span></td>
          <td class="px-4 py-2.5 text-slate-600 font-mono text-[11px]">${m.dt_code}</td>
        </tr>`;
      }).join('');
    }

    async function selectMeter(meterId) {
      state.selectedMeterId = meterId;
      // Re-highlight table rows
      document.querySelectorAll('#meters-table-body tr').forEach(row => {
        if (row.innerHTML.includes(meterId)) {
          row.className = 'cursor-pointer transition bg-blue-50/70 font-semibold';
        } else {
          row.className = 'cursor-pointer transition hover:bg-slate-50';
        }
      });

      const res = await fetch('/api/v1/meters/' + meterId);
      if (!res.ok) return;
      const meter = await res.json();

      document.getElementById('detail-id').textContent = meter.meter_id;
      document.getElementById('detail-serial').textContent = 'Serial: ' + meter.serial_number;
      document.getElementById('spec-make').textContent = meter.make;
      document.getElementById('spec-phase').textContent = meter.phase_type;
      document.getElementById('spec-type').textContent = meter.install_type || 'N/A';
      document.getElementById('spec-build').textContent = meter.build_type || 'N/A';
      document.getElementById('spec-dt').textContent = meter.dt_code;
      
      const geoText = meter.geo ? `${meter.geo.latitude.toFixed(4)}, ${meter.geo.longitude.toFixed(4)}` : 'N/A';
      document.getElementById('spec-geo').textContent = geoText;

      const breadcrumb = document.getElementById('hierarchy-breadcrumbs');
      if (meter.hierarchy) {
        const parts = [
          meter.hierarchy.zone.name,
          meter.hierarchy.circle.name,
          meter.hierarchy.division.name,
          meter.hierarchy.substation.name,
          meter.hierarchy.feeder.name,
          meter.hierarchy.dt.name
        ];
        breadcrumb.innerHTML = parts.map((p, i) => `<span>${p}</span>${i < parts.length - 1 ? '<span class="text-slate-300">›</span>' : ''}`).join('');
      } else {
        breadcrumb.innerHTML = '<span class="text-slate-400">No hierarchy available</span>';
      }

      document.getElementById('detail-content').classList.remove('hidden');
      loadConsumption(meterId);
    }

    async function loadConsumption(meterId) {
      try {
        const res = await fetch('/api/v1/meters/' + meterId + '/consumption');
        const json = await res.json();
        const readings = json.data || [];
        
        // Take last 48 readings for clean chart (24 hours)
        const recent = readings.slice(-48);
        const labels = recent.map(r => r.timestamp.slice(11, 16));
        const values = recent.map(r => r.kwh);

        const ctx = document.getElementById('consumptionChart').getContext('2d');
        if (state.chartInstance) {
          state.chartInstance.destroy();
        }

        state.chartInstance = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [{
              label: 'Active Energy (kWh)',
              data: values,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2,
              fill: true,
              tension: 0.2,
              pointRadius: 0
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              x: { grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 9 } } },
              y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 } } }
            }
          }
        });
      } catch (err) {
        console.error('Failed to load consumption chart', err);
      }
    }

    // Event listeners
    document.getElementById('search-input').addEventListener('input', () => { state.page = 1; fetchMeters(); });
    document.getElementById('filter-status').addEventListener('change', () => { state.page = 1; fetchMeters(); });
    document.getElementById('filter-make').addEventListener('change', () => { state.page = 1; fetchMeters(); });
    document.getElementById('btn-prev').addEventListener('click', () => { if (state.page > 1) { state.page--; fetchMeters(); } });
    document.getElementById('btn-next').addEventListener('click', () => { if (state.page < state.totalPages) { state.page++; fetchMeters(); } });

    loadHealth();
    fetchMeters();
  </script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def get_dashboard():
    """Serves the interactive web explorer for meters, telemetry, and network hierarchy."""
    return HTMLResponse(content=HTML_CONTENT)
