import os

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Agent Configuration</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #00051e; --surface: #0a0f2b; --surface2: #141938;
      --border: #1e2345; --accent: #facc15; --green: #10b981;
      --text: #ffffff; --muted: #a1a1aa;
    }
    body {
      font-family: 'Inter', sans-serif;
      margin: 0; padding: 0;
      color: var(--text); background: var(--bg);
      display: flex; height: 100vh; overflow: hidden;
    }
    .sidebar {
      width: 260px;
      position: fixed;
      top: 0;
      left: 0;
      height: 100vh;
      overflow-y: auto;
      background: var(--bg);
      border-right: 1px solid var(--border);
      display: flex; flex-direction: column;
      padding: 32px 0;
    }
    .sidebar-nav {
      display: flex; flex-direction: column;
      gap: 16px; margin-top: 40px;
    }
    .sidebar-link {
        display: block;
        padding: 14px 32px;
        color: var(--text);
        text-decoration: none;
        font-weight: 500;
        font-size: 16px;
        transition: all 0.2s;
        border-left: 4px solid transparent;
      }
      .sidebar-link:hover {
        background: rgba(255,255,255,0.05);
        border-left: 4px solid var(--accent);
      }
      .sidebar-link.active {
        font-weight: 700;
        background: rgba(255,255,255,0.1);
        border-left: 4px solid var(--accent);
      }
    .main-content {
      flex: 1;
      padding: 40px;
      margin-left: 260px;
      height: 100vh;
      overflow-y: auto;
      box-sizing: border-box;
    }
    .page-body { max-width: 800px; }
    h1 { font-size: 24px; margin-bottom: 24px; }
    .form-group { margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
    label { font-size: 14px; color: var(--text); }
    input {
      width: 100px; padding: 8px; background: var(--surface); color: var(--text);
      border: 1px solid var(--border); border-radius: 6px; font-family: inherit; text-align: right;
    }
    button {
      background: var(--accent); color: #000; padding: 10px 20px;
      border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
      margin-top: 20px; width: 100%;
    }
    button:hover:not(:disabled) { opacity: 0.9; }
    button:disabled { background: #555; color: #888; cursor: not-allowed; }
    .status-msg { margin-top: 16px; font-size: 14px; text-align: center; }
    .success { color: var(--green); }
    .error { color: #ef4444; }
    .total-row {
      margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
      font-weight: 700; font-size: 18px;
    }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div style="padding: 0 32px; display: flex; align-items: center; justify-content: center;">
        <img src="intelligenz-logo.png" alt="Intelligenz IT Logo" style="max-width: 180px;">
    </div>
    <nav class="sidebar-nav">
      <a href="/widget/demo.html" class="sidebar-link">Dashboard</a>
      <a href="/widget/onboarding.html" class="sidebar-link">Onboard Agent</a>
      <a href="/widget/configuration.html" class="sidebar-link active">Configuration</a>
      <a href="/widget/score.html" class="sidebar-link">Rating</a>
      <a href="/widget/agent-profile.html" class="sidebar-link">Profile</a>
      <a href="/widget/resources.html" class="sidebar-link">Resources</a>
      <a href="/widget/logout.html" class="sidebar-link">Sign Out</a>
    </nav>
  </aside>
  <main class="main-content">
    <div class="page-body">
      <h2 style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Agent Dynamic Weightage Configuration</h2>
      <div style="margin-bottom: 20px;">
         <label style="display:block; margin-bottom: 6px;">Agent ID</label>
         <input type="text" id="agent_id" required style="width: 100%; text-align: left;" placeholder="agent-001">
      </div>
      <form id="configForm">
        <div class="form-group">
          <label>Productivity (P)</label>
          <div><input type="number" id="weight_p" value="14.28" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Quality (Q)</label>
          <div><input type="number" id="weight_q" value="14.28" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Execution (E)</label>
          <div><input type="number" id="weight_e" value="14.28" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Validation (V)</label>
          <div><input type="number" id="weight_v" value="14.28" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Risk (R)</label>
          <div><input type="number" id="weight_r" value="14.29" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Governance (G)</label>
          <div><input type="number" id="weight_g" value="14.29" step="0.01" min="0" max="100"> %</div>
        </div>
        <div class="form-group">
          <label>Cost (C)</label>
          <div><input type="number" id="weight_c" value="14.30" step="0.01" min="0" max="100"> %</div>
        </div>
        
        <div class="total-row">
          <span>Total Weight:</span>
          <span id="total_weight">100.00%</span>
        </div>

        <button type="submit" id="saveBtn">Save Configuration</button>
        <div id="status" class="status-msg"></div>
      </form>
    </div>

    <script>
      function updateTotal() {
        const p = parseFloat(document.getElementById('weight_p').value) || 0;
        const q = parseFloat(document.getElementById('weight_q').value) || 0;
        const e = parseFloat(document.getElementById('weight_e').value) || 0;
        const v = parseFloat(document.getElementById('weight_v').value) || 0;
        const r = parseFloat(document.getElementById('weight_r').value) || 0;
        const g = parseFloat(document.getElementById('weight_g').value) || 0;
        const c = parseFloat(document.getElementById('weight_c').value) || 0;
        
        const total = p + q + e + v + r + g + c;
        const totalEl = document.getElementById('total_weight');
        const saveBtn = document.getElementById('saveBtn');
        
        totalEl.textContent = total.toFixed(2) + '%';
        
        if (Math.abs(total - 100.0) < 0.01) {
            totalEl.style.color = 'var(--green)';
            saveBtn.disabled = false;
        } else {
            totalEl.style.color = 'var(--accent)';
            saveBtn.disabled = true;
        }
      }

      const inputs = document.querySelectorAll('input[type="number"]');
      inputs.forEach(inp => inp.addEventListener('input', updateTotal));

      const params = new URLSearchParams(window.location.search);
      const urlAgent = params.get('agent_id');
      if (urlAgent) {
          document.getElementById('agent_id').value = urlAgent;
      }
      
      // Auto-fetch if exists
      async function loadWeights() {
          const agentId = document.getElementById('agent_id').value.trim();
          if(!agentId) return;
          try {
              const res = await fetch(`/api/agents/${agentId}/weightages`);
              if (res.ok) {
                  const data = await res.json();
                  document.getElementById('weight_p').value = data.weight_p;
                  document.getElementById('weight_q').value = data.weight_q;
                  document.getElementById('weight_e').value = data.weight_e;
                  document.getElementById('weight_v').value = data.weight_v;
                  document.getElementById('weight_r').value = data.weight_r;
                  document.getElementById('weight_g').value = data.weight_g;
                  document.getElementById('weight_c').value = data.weight_c;
                  updateTotal();
              }
          } catch(e) {}
      }
      document.getElementById('agent_id').addEventListener('change', loadWeights);
      if (urlAgent) loadWeights();

      document.getElementById('configForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const agentId = document.getElementById('agent_id').value.trim();
        if(!agentId) return alert("Agent ID required");

        const payload = {
          weight_p: parseFloat(document.getElementById('weight_p').value),
          weight_q: parseFloat(document.getElementById('weight_q').value),
          weight_e: parseFloat(document.getElementById('weight_e').value),
          weight_v: parseFloat(document.getElementById('weight_v').value),
          weight_r: parseFloat(document.getElementById('weight_r').value),
          weight_g: parseFloat(document.getElementById('weight_g').value),
          weight_c: parseFloat(document.getElementById('weight_c').value)
        };
        
        const statusEl = document.getElementById('status');
        statusEl.textContent = 'Saving...';
        statusEl.className = 'status-msg';

        try {
          const res = await fetch(`/api/agents/${agentId}/weightages`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (res.ok) {
              statusEl.textContent = 'Configuration saved successfully!';
              statusEl.classList.add('success');
              setTimeout(() => { window.location.href = `/widget/agent-profile.html?id=${agentId}`; }, 1000);
          } else {
              const err = await res.json();
              statusEl.textContent = 'Error: ' + err.detail;
              statusEl.classList.add('error');
          }
        } catch (err) {
          statusEl.textContent = 'Error: ' + err.message;
          statusEl.classList.add('error');
        }
      });
      updateTotal();
    </script>
  </main>
</body>
</html>
"""

with open('widget/configuration.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
