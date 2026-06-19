"""Mock services for Prometheus (9090), Grafana (3000), Langfuse (4000), and OpenTelemetry (4317).

Provides beautiful, premium, interactive dashboards for native Windows environments.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import os
import sqlite3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

def get_latest_data():
    try:
        db_path = "d:\\Projects\\widget\\widget\\dpi_ls.db"
        if not os.path.exists(db_path):
            db_path = "dpi_ls.db"
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT score, raw_score, breakdown, details, created_at FROM score_history WHERE agent_id='chandra-finops' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        score = 94.42
        model_cost = 1.24
        human_cost = 50.0
        total_cost = 51.24
        input_tokens = 120000
        output_tokens = 40000
        required = 2
        validated = 2
        accuracy = 0.93
        hallucination = 0.05
        
        if row:
            score = row[0]
            try:
                details = json.loads(row[3])
                cost_dict = details.get("C", {})
                model_cost = cost_dict.get("model_cost", 1.24)
                human_cost = cost_dict.get("Human_cost", 50.0)
                total_cost = model_cost + human_cost
                input_tokens = cost_dict.get("input_tokens", 120000)
                output_tokens = cost_dict.get("output_tokens", 40000)
                
                val_dict = details.get("V", {})
                required = val_dict.get("required_components", 2)
                validated = val_dict.get("validated_components", 2)
                
                q_dict = details.get("Q", {})
                accuracy = q_dict.get("accuracy", 0.93)
                hallucination = q_dict.get("hallucination_rate", 0.05)
            except Exception:
                pass
        conn.close()
        return {
            "score": score,
            "model_cost": model_cost,
            "human_cost": human_cost,
            "total_cost": total_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "required": required,
            "validated": validated,
            "accuracy": accuracy,
            "hallucination": hallucination
        }
    except Exception:
        return {
            "score": 94.42,
            "model_cost": 1.24,
            "human_cost": 50.0,
            "total_cost": 51.24,
            "input_tokens": 120000,
            "output_tokens": 40000,
            "required": 2,
            "validated": 2,
            "accuracy": 0.93,
            "hallucination": 0.05
        }

# Common premium CSS style to share across all dashboards for visual consistency and premium feel
SHARED_STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {
  --bg: #090a0f;
  --panel-bg: rgba(20, 22, 37, 0.6);
  --border: rgba(255, 255, 255, 0.08);
  --text: #f3f4f6;
  --muted: #9ca3af;
  --accent: #ff4d4d;
  --success: #10b981;
  --warning: #f59e0b;
  --glow-green: 0 0 20px rgba(16, 185, 129, 0.3);
  --glow-orange: 0 0 20px rgba(245, 158, 11, 0.3);
  --glow-blue: 0 0 20px rgba(59, 130, 246, 0.3);
  --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
body {
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  background-image: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                    radial-gradient(circle at 90% 80%, rgba(219, 39, 119, 0.08) 0%, transparent 40%);
  color: var(--text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  padding: 20px 40px;
  background: rgba(13, 14, 24, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo-container {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 18px;
  box-shadow: var(--glow-blue);
}
h1 {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: var(--success);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  box-shadow: var(--glow-green);
}
.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1.1); opacity: 0.5; box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
main {
  flex: 1;
  padding: 40px;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
}
.grid {
  display: grid;
  gap: 24px;
}
.card {
  background: var(--panel-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--card-shadow);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.3s ease;
}
.card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.15);
}
.card-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  font-weight: 600;
  margin-bottom: 16px;
}
/* Buttons */
.btn {
  background: linear-gradient(135deg, #4f46e5, #06b6d4);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}
.btn:hover {
  opacity: 0.9;
  transform: scale(1.02);
}
.btn:active {
  transform: scale(0.98);
}
/* Console / Terminal */
.console {
  background: #050608;
  border: 1px solid var(--border);
  border-radius: 12px;
  font-family: 'JetBrains Mono', monospace;
  padding: 20px;
  font-size: 13px;
  color: #10b981;
  overflow-y: auto;
  height: 250px;
  line-height: 1.6;
}
.console-line {
  margin-bottom: 4px;
}
.console-line .time {
  color: #6b7280;
  margin-right: 12px;
}
.console-line .info {
  color: #3b82f6;
}
.console-line .warn {
  color: #f59e0b;
}
"""

def get_prometheus_html(data) -> str:
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Prometheus Time-Series Expression Browser</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --accent: #e6522c;
      --glow-blue: 0 0 20px rgba(230, 82, 44, 0.3);
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #e6522c, #ff7e47);
    }}
    .search-row {{
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .input-field {{
      flex: 1;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }}
    .input-field:focus {{
      border-color: var(--accent);
    }}
    .metric-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }}
    .metric-tag {{
      background: rgba(230, 82, 44, 0.1);
      border: 1px solid rgba(230, 82, 44, 0.2);
      color: #ff7e47;
      padding: 4px 10px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .metric-tag:hover {{
      background: rgba(230, 82, 44, 0.2);
    }}
    .targets-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }}
    .targets-table th, .targets-table td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    .targets-table th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .targets-table td {{
      font-size: 13px;
    }}
    .nav-tab-link:hover {{
      background: rgba(255,255,255,0.05);
      color: #fff !important;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo-container">
      <div class="logo-icon">P</div>
      <div>
        <h1 style="font-size: 20px; font-weight: 700;">Prometheus</h1>
        <div style="font-size:12px; color:var(--muted)">Time-Series Metrics</div>
      </div>
    </div>
    <div class="nav-tabs" style="display:flex; gap:16px; margin-left:40px;">
      <a href="/" class="nav-tab-link" style="color:#ff7e47; background: rgba(230, 82, 44, 0.1); border: 1px solid rgba(230, 82, 44, 0.2); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px;">Graph</a>
      <a href="/targets" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Targets</a>
      <a href="/service-discovery" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Service Discovery</a>
    </div>
    <div class="status-badge" style="margin-left:auto;">
      <div class="pulse-dot"></div>
      Server UP (Port 9090)
    </div>
  </header>
  <main>
    <div class="grid" style="grid-template-columns: 2fr 1fr;">
      <div class="stack" style="display:flex; flex-direction:column; gap:24px">
        <div class="card">
          <div class="card-title">Expression Query</div>
          <div class="search-row">
            <input type="text" class="input-field" id="expr" value="model_cost{{"agent_id"="chandra-finops"}}" placeholder="Enter Prometheus expression...">
            <button class="btn" onclick="runQuery()">Execute</button>
          </div>
          <div style="font-size:12px; color:var(--muted); margin-bottom:8px">Quick Metrics Selector:</div>
          <div class="metric-list">
            <div class="metric-tag" onclick="selectExpr('model_cost')">model_cost</div>
            <div class="metric-tag" onclick="selectExpr('token_cost')">token_cost</div>
            <div class="metric-tag" onclick="selectExpr('prompt_cost')">prompt_cost</div>
            <div class="metric-tag" onclick="selectExpr('completion_cost')">completion_cost</div>
            <div class="metric-tag" onclick="selectExpr('validation_score')">validation_score</div>
            <div class="metric-tag" onclick="selectExpr('total_cost_of_ownership')">total_cost_of_ownership</div>
          </div>
        </div>

        <div class="card" style="flex:1;">
          <div class="card-title">Graph Visualization</div>
          <div style="height: 300px; display:flex; align-items:center; justify-content:center; border:1px dashed var(--border); border-radius:12px; background:rgba(0,0,0,0.2); position:relative; overflow:hidden">
            <svg id="chart" style="width:100%; height:100%; display:none" viewBox="0 0 800 300">
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.2"/>
                  <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <!-- Grid lines -->
              <line x1="50" y1="50" x2="750" y2="50" stroke="var(--border)" stroke-dasharray="4"/>
              <line x1="50" y1="125" x2="750" y2="125" stroke="var(--border)" stroke-dasharray="4"/>
              <line x1="50" y1="200" x2="750" y2="200" stroke="var(--border)" stroke-dasharray="4"/>
              <line x1="50" y1="275" x2="750" y2="275" stroke="var(--border)"/>
              
              <!-- Labels -->
              <text x="20" y="55" fill="var(--muted)" font-size="10">1.5</text>
              <text x="20" y="130" fill="var(--muted)" font-size="10">1.0</text>
              <text x="20" y="205" fill="var(--muted)" font-size="10">0.5</text>
              <text x="20" y="280" fill="var(--muted)" font-size="10">0.0</text>
              
              <!-- Plot -->
              <path id="graph-area" fill="url(#grad)" d=""/>
              <path id="graph-line" fill="none" stroke="var(--accent)" stroke-width="3" d=""/>
              
              <!-- Data points -->
              <circle cx="100" cy="238" r="4" fill="var(--text)"/>
              <circle cx="230" cy="208" r="4" fill="var(--text)"/>
              <circle cx="360" cy="148" r="4" fill="var(--text)"/>
              <circle cx="490" cy="118" r="4" fill="var(--text)"/>
              <circle cx="620" cy="89" r="4" fill="var(--text)"/>
              <circle cx="750" cy="89" r="4" fill="var(--text)"/>
            </svg>
            <div id="no-data" style="color:var(--muted); font-size:14px; text-align:center">
              Click <strong>Execute</strong> to query and view metric time-series graph.
            </div>
          </div>
        </div>
      </div>

      <div class="stack" style="display:flex; flex-direction:column; gap:24px">
        <div class="card">
          <div class="card-title">Scrape Targets (UP)</div>
          <table class="targets-table">
            <thead>
              <tr>
                <th>Endpoint</th>
                <th>Status</th>
                <th>Last Scrape</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="color:#06b6d4; font-family:monospace">dpi-ls:8000/metrics</td>
                <td><span style="color:var(--success); font-weight:600">UP</span></td>
                <td id="scrape-time">1.2s ago</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">Scrape Console Log</div>
          <div class="console" id="log-box"></div>
        </div>
      </div>
    </div>
  </main>
  
  <script>
    function selectExpr(metric) {{
      document.getElementById('expr').value = metric + '{{agent_id="chandra-finops"}}';
    }}

    function runQuery() {{
      const noData = document.getElementById('no-data');
      const chart = document.getElementById('chart');
      
      noData.style.display = 'none';
      chart.style.display = 'block';
      
      const expr = document.getElementById('expr').value;
      
      // Animate line based on metric
      let points = [];
      if (expr.includes('validation_score')) {{
        points = [[100, 275], [230, 200], [360, 125], [490, 50], [620, 50], [750, 50]];
      }} else if (expr.includes('model_cost') || expr.includes('total_cost_of_ownership')) {{
        points = [[100, 238], [230, 208], [360, 148], [490, 118], [620, 89], [750, 89]];
      }} else {{
        points = [[100, 250], [230, 260], [360, 180], [490, 150], [620, 130], [750, 100]];
      }}
      
      let linePath = "M " + points[0][0] + " " + points[0][1];
      for(let i=1; i<points.length; i++) {{
        linePath += " L " + points[i][0] + " " + points[i][1];
      }}
      
      let areaPath = linePath + " L " + points[points.length-1][0] + " 275 L " + points[0][0] + " 275 Z";
      
      document.getElementById('graph-line').setAttribute('d', linePath);
      document.getElementById('graph-area').setAttribute('d', areaPath);
      
      addConsoleLine("Query executed successfully: " + expr);
    }}

    const logBox = document.getElementById('log-box');
    function addConsoleLine(msg) {{
      const time = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'console-line';
      div.innerHTML = `<span class="time">[${{time}}]</span><span class="info">INFO</span> ${{msg}}`;
      logBox.appendChild(div);
      logBox.scrollTop = logBox.scrollHeight;
    }}

    // Simulate targets scraping log
    setInterval(() => {{
      addConsoleLine("Scraped target http://localhost:8000/metrics (HTTP 200)");
      document.getElementById('scrape-time').innerText = "0.1s ago";
    }}, 4000);
    
    // Seed initial logs
    addConsoleLine("Prometheus server initialized");
    addConsoleLine("Discovered target: http://localhost:8000/metrics");
    addConsoleLine("Scraped target http://localhost:8000/metrics (HTTP 200)");
  </script>
</body>
</html>
"""

def get_prometheus_targets_html(data) -> str:
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Prometheus Scrape Targets</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --accent: #e6522c;
      --glow-blue: 0 0 20px rgba(230, 82, 44, 0.3);
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #e6522c, #ff7e47);
    }}
    .nav-tab-link:hover {{
      background: rgba(255,255,255,0.05);
      color: #fff !important;
    }}
    .targets-group {{
      margin-bottom: 30px;
    }}
    .targets-group-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 12px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
    }}
    .targets-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
    }}
    .targets-table th, .targets-table td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    .targets-table th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .targets-table td {{
      font-size: 13px;
    }}
    .label-badge {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: #f3f4f6;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 11px;
      margin-right: 4px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo-container">
      <div class="logo-icon">P</div>
      <div>
        <h1 style="font-size: 20px; font-weight: 700;">Prometheus</h1>
        <div style="font-size:12px; color:var(--muted)">Time-Series Metrics</div>
      </div>
    </div>
    <div class="nav-tabs" style="display:flex; gap:16px; margin-left:40px;">
      <a href="/" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Graph</a>
      <a href="/targets" class="nav-tab-link" style="color:#ff7e47; background: rgba(230, 82, 44, 0.1); border: 1px solid rgba(230, 82, 44, 0.2); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px;">Targets</a>
      <a href="/service-discovery" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Service Discovery</a>
    </div>
    <div class="status-badge" style="margin-left:auto;">
      <div class="pulse-dot"></div>
      Server UP (Port 9090)
    </div>
  </header>
  
  <main>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <h2 style="font-size: 22px; font-weight: 700; color: #fff;">Targets</h2>
      <div style="font-size: 13px; color: var(--muted);">
        Show: <span style="color:#ff7e47; font-weight:600; cursor:pointer;">All (4)</span> | <span style="cursor:pointer;">Active (4)</span> | <span style="cursor:pointer;">Dropped (0)</span>
      </div>
    </div>

    <!-- Target Group 1 -->
    <div class="targets-group">
      <div class="targets-group-header">
        <span>chandra-finops-backend</span>
        <span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-size: 12px; padding: 2px 8px; border-radius: 20px; font-weight: 600;">1 / 1 UP</span>
      </div>
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="targets-table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>State</th>
              <th>Labels</th>
              <th>Last Scrape</th>
              <th>Scrape Duration</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="color:#06b6d4; font-family:monospace; font-weight:600;">http://localhost:8000/metrics</td>
              <td><span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-weight:600; padding: 2px 6px; border-radius: 4px;">UP</span></td>
              <td>
                <span class="label-badge">instance="localhost:8000"</span>
                <span class="label-badge">job="chandra-finops-backend"</span>
                <span class="label-badge">env="local"</span>
              </td>
              <td>1.2s ago</td>
              <td>4.2ms</td>
              <td style="color:var(--muted)">None</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Target Group 2 -->
    <div class="targets-group">
      <div class="targets-group-header">
        <span>arize-phoenix</span>
        <span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-size: 12px; padding: 2px 8px; border-radius: 20px; font-weight: 600;">1 / 1 UP</span>
      </div>
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="targets-table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>State</th>
              <th>Labels</th>
              <th>Last Scrape</th>
              <th>Scrape Duration</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="color:#06b6d4; font-family:monospace; font-weight:600;">http://localhost:6006/metrics</td>
              <td><span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-weight:600; padding: 2px 6px; border-radius: 4px;">UP</span></td>
              <td>
                <span class="label-badge">instance="localhost:6006"</span>
                <span class="label-badge">job="arize-phoenix"</span>
              </td>
              <td>0.8s ago</td>
              <td>3.1ms</td>
              <td style="color:var(--muted)">None</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Target Group 3 -->
    <div class="targets-group">
      <div class="targets-group-header">
        <span>mlflow</span>
        <span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-size: 12px; padding: 2px 8px; border-radius: 20px; font-weight: 600;">1 / 1 UP</span>
      </div>
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="targets-table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>State</th>
              <th>Labels</th>
              <th>Last Scrape</th>
              <th>Scrape Duration</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="color:#06b6d4; font-family:monospace; font-weight:600;">http://localhost:5000/metrics</td>
              <td><span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-weight:600; padding: 2px 6px; border-radius: 4px;">UP</span></td>
              <td>
                <span class="label-badge">instance="localhost:5000"</span>
                <span class="label-badge">job="mlflow"</span>
              </td>
              <td>2.4s ago</td>
              <td>5.0ms</td>
              <td style="color:var(--muted)">None</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Target Group 4 -->
    <div class="targets-group">
      <div class="targets-group-header">
        <span>otel-collector</span>
        <span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-size: 12px; padding: 2px 8px; border-radius: 20px; font-weight: 600;">1 / 1 UP</span>
      </div>
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="targets-table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>State</th>
              <th>Labels</th>
              <th>Last Scrape</th>
              <th>Scrape Duration</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="color:#06b6d4; font-family:monospace; font-weight:600;">http://localhost:4318/metrics</td>
              <td><span style="background: rgba(16, 185, 129, 0.15); color: var(--success); font-weight:600; padding: 2px 6px; border-radius: 4px;">UP</span></td>
              <td>
                <span class="label-badge">instance="localhost:4318"</span>
                <span class="label-badge">job="otel-collector"</span>
              </td>
              <td>1.8s ago</td>
              <td>6.2ms</td>
              <td style="color:var(--muted)">None</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>
</body>
</html>
"""

def get_prometheus_sd_html(data) -> str:
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Prometheus Service Discovery</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --accent: #e6522c;
      --glow-blue: 0 0 20px rgba(230, 82, 44, 0.3);
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #e6522c, #ff7e47);
    }}
    .nav-tab-link:hover {{
      background: rgba(255,255,255,0.05);
      color: #fff !important;
    }}
    .sd-card {{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 16px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo-container">
      <div class="logo-icon">P</div>
      <div>
        <h1 style="font-size: 20px; font-weight: 700;">Prometheus</h1>
        <div style="font-size:12px; color:var(--muted)">Time-Series Metrics</div>
      </div>
    </div>
    <div class="nav-tabs" style="display:flex; gap:16px; margin-left:40px;">
      <a href="/" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Graph</a>
      <a href="/targets" class="nav-tab-link" style="color:var(--muted); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px; transition: all 0.2s;">Targets</a>
      <a href="/service-discovery" class="nav-tab-link" style="color:#ff7e47; background: rgba(230, 82, 44, 0.1); border: 1px solid rgba(230, 82, 44, 0.2); text-decoration:none; font-size:14px; font-weight:600; padding:6px 12px; border-radius:4px;">Service Discovery</a>
    </div>
    <div class="status-badge" style="margin-left:auto;">
      <div class="pulse-dot"></div>
      Server UP (Port 9090)
    </div>
  </header>
  
  <main>
    <h2 style="font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 24px;">Service Discovery Status</h2>

    <div class="sd-card">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 600; font-size: 15px; color: #fff;">static_configs (4 active groups)</span>
        <span style="color: var(--success); font-size: 12px; font-weight: 600;">ACTIVE</span>
      </div>
      <div style="font-size: 13px; color: var(--muted); margin-top: 10px; line-height: 1.6;">
        Prometheus has discovered 4 target configurations statically via local daemon config.
        <ul style="margin-left: 20px; margin-top: 8px;">
          <li>chandra-finops-backend: Discovered 1 target (http://localhost:8000/metrics)</li>
          <li>arize-phoenix: Discovered 1 target (http://localhost:6006/metrics)</li>
          <li>mlflow: Discovered 1 target (http://localhost:5000/metrics)</li>
          <li>otel-collector: Discovered 1 target (http://localhost:4318/metrics)</li>
        </ul>
      </div>
    </div>
  </main>
</body>
</html>
"""


def get_grafana_html(data) -> str:
  val_pct = (data['validated'] / max(data['required'], 1)) * 100
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Grafana - DPI-LS Digital FTE Scorecard</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --bg: #111217;
      --panel-bg: #181b1f;
      --border: #2c323d;
      --accent: #f99f1b;
      --glow-blue: 0 0 20px rgba(249, 159, 27, 0.2);
    }}
    body {{
      flex-direction: row !important;
    }}
    header {{
      background: #181b1f;
      border-bottom: 2px solid #202226;
      width: 100%;
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #f99f1b, #f97316);
      color: #111217;
    }}
    .menu-item:hover {{
      background: rgba(255, 255, 255, 0.03);
      color: var(--text) !important;
    }}
    .metric-value {{
      font-size: 32px;
      font-weight: 700;
      color: #ffffff;
      margin-top: 8px;
    }}
    .metric-sub {{
      font-size: 12px;
      color: var(--success);
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
      margin-bottom: 24px;
    }}
    @media (max-width: 1024px) {{
      .panel-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
    }}
  </style>
</head>
<body>
  <!-- LEFT SIDEBAR -->
  <div class="sidebar" style="width: 250px; background: #111217; border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; padding: 20px 10px; gap: 20px;">
    <div class="logo-container" style="display: flex; align-items: center; gap: 12px; padding: 0 10px;">
      <div class="logo-icon" style="background: linear-gradient(135deg, #f99f1b, #f97316); color: #111217; width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px;">G</div>
      <h1 style="font-size: 18px; font-weight: 700; color: #fff;">Grafana</h1>
    </div>
    <div class="sidebar-menu" style="display: flex; flex-direction: column; gap: 6px;">
      <a href="/" class="menu-item active" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; color: #c084fc; background: rgba(249, 159, 27, 0.1); border: 1px solid rgba(249, 159, 27, 0.2); text-decoration: none;">
        <span class="menu-item-icon">📊</span> Dashboards
      </a>
      <a href="/datasources" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">🔌</span> Data Sources
      </a>
      <a href="http://localhost:8000/widget/resources.html" target="_blank" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">📋</span> Resource Eval UI
      </a>
      <a href="/explore" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">🔍</span> Explore
      </a>
    </div>
    <div class="sidebar-footer" style="margin-top: auto; padding: 10px; font-size: 11px; color: var(--muted); border-top: 1px solid var(--border);">
      <div>Grafana v10.4.1</div>
      <div>Local Host Integration</div>
    </div>
  </div>

  <!-- MAIN CONTENT AREA -->
  <div class="content-area" style="flex: 1; display: flex; flex-direction: column; overflow-y: auto;">
    <header>
      <div class="logo-container">
        <div>
          <h1>Grafana - DPI-LS scorecard Dashboard</h1>
          <div style="font-size:12px; color:var(--muted)">Home / Dashboards / AI Agents / Digital FTE Index</div>
        </div>
      </div>
      <div class="status-badge">
        <div class="pulse-dot"></div>
        Grafana Live (Port 3000)
      </div>
    </header>
    <main>
      <div class="panel-grid">
        <div class="card">
          <div class="card-title">Digital FTE composite score</div>
          <div class="metric-value" style="color:var(--success)">{data['score']:.2f} <span style="font-size:14px; font-weight:400; color:var(--muted)">/ 100</span></div>
          <div class="metric-sub">
            <span style="font-size:14px">▲</span> 2.1% improvement (last 24h)
          </div>
        </div>

        <div class="card">
          <div class="card-title">Total Cost of Ownership (TCO)</div>
          <div class="metric-value">${data['total_cost']:.2f} <span style="font-size:14px; font-weight:400; color:var(--muted)">/ task</span></div>
          <div class="metric-sub" style="color:#06b6d4">
            <span>▼</span> -12.4% cost reduction
          </div>
        </div>

        <div class="card">
          <div class="card-title">Validation Compliance</div>
          <div class="metric-value">{val_pct:.1f}%</div>
          <div class="metric-sub">
            <span>✓</span> Audit checklist fully compliant
          </div>
        </div>

        <div class="card">
          <div class="card-title">Metric Scraping Rate</div>
          <div class="metric-value">0.33 <span style="font-size:14px; font-weight:400; color:var(--muted)">req / sec</span></div>
          <div class="metric-sub">
            <span>✓</span> Active (Prometheus metrics collector)
          </div>
        </div>
      </div>

      <div class="grid" style="grid-template-columns: 2fr 1fr; gap:20px">
        <div class="card" style="height: 400px; display:flex; flex-direction:column">
          <div class="card-title">Dimension Breakdown Over Time</div>
          <div style="flex:1; border:1px solid var(--border); border-radius:12px; background:rgba(0,0,0,0.15); padding:10px; overflow:hidden">
            <svg style="width:100%; height:100%" viewBox="0 0 800 300">
              <!-- Grid lines -->
              <line x1="50" y1="50" x2="750" y2="50" stroke="#222" />
              <line x1="50" y1="125" x2="750" y2="125" stroke="#222" />
              <line x1="50" y1="200" x2="750" y2="200" stroke="#222" />
              <line x1="50" y1="275" x2="750" y2="275" stroke="var(--border)" />
              
              <!-- Curves -->
              <!-- Q (Quality): teal -->
              <path fill="none" stroke="#06b6d4" stroke-width="2.5" d="M 50 150 Q 200 130 350 90 T 700 80" />
              <!-- G (Governance): green -->
              <path fill="none" stroke="var(--success)" stroke-width="2.5" d="M 50 90 Q 200 85 350 75 T 700 75" />
              <!-- C (Cost): orange -->
              <path fill="none" stroke="var(--accent)" stroke-width="2.5" d="M 50 220 Q 200 210 350 180 T 700 120" />
              
              <circle cx="700" cy="80" r="4" fill="#06b6d4"/>
              <circle cx="700" cy="75" r="4" fill="var(--success)"/>
              <circle cx="700" cy="120" r="4" fill="var(--accent)"/>

              <legend>
                <text x="60" y="40" fill="var(--success)" font-size="11">Governance (G)</text>
                <text x="200" y="40" fill="#06b6d4" font-size="11">Quality (Q)</text>
                <text x="320" y="40" fill="var(--accent)" font-size="11">Cost (C)</text>
              </legend>
            </svg>
          </div>
        </div>

        <div class="card" style="display:flex; flex-direction:column">
          <div class="card-title">Prometheus Targets Status</div>
          <div style="flex:1; display:flex; flex-direction:column; gap:12px; justify-content:center">
            <div style="display:flex; justify-content:space-between; padding:12px; background:rgba(255,255,255,0.02); border-radius:8px; border-left:4px solid var(--success)">
              <div>
                <div style="font-weight:600; font-size:14px">prometheus_endpoint</div>
                <div style="font-size:11px; color:var(--muted)">http://localhost:8000/metrics</div>
              </div>
              <div style="color:var(--success); font-weight:600; font-size:13px">ONLINE</div>
            </div>
            
            <div style="display:flex; justify-content:space-between; padding:12px; background:rgba(255,255,255,0.02); border-radius:8px; border-left:4px solid var(--success)">
              <div>
                <div style="font-weight:600; font-size:14px">otel_exporter_endpoint</div>
                <div style="font-size:11px; color:var(--muted)">http://localhost:4317</div>
              </div>
              <div style="color:var(--success); font-weight:600; font-size:13px">ONLINE</div>
            </div>

            <div style="display:flex; justify-content:space-between; padding:12px; background:rgba(255,255,255,0.02); border-radius:8px; border-left:4px solid var(--success)">
              <div>
                <div style="font-weight:600; font-size:14px">langfuse_webhook</div>
                <div style="font-size:11px; color:var(--muted)">http://localhost:4000</div>
              </div>
              <div style="color:var(--success); font-weight:600; font-size:13px">ONLINE</div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</body>
</html>
"""

def get_grafana_datasources_html(data) -> str:
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Grafana - Data Sources Configuration</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --bg: #111217;
      --panel-bg: #181b1f;
      --border: #2c323d;
      --accent: #f99f1b;
      --glow-blue: 0 0 20px rgba(249, 159, 27, 0.2);
    }}
    body {{
      flex-direction: row !important;
    }}
    header {{
      background: #181b1f;
      border-bottom: 2px solid #202226;
      width: 100%;
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #f99f1b, #f97316);
      color: #111217;
    }}
    .menu-item:hover {{
      background: rgba(255, 255, 255, 0.03);
      color: var(--text) !important;
    }}
    .ds-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }}
    .ds-table th, .ds-table td {{
      padding: 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    .ds-table th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      font-weight: 600;
    }}
    .ds-table tr:hover {{
      background: rgba(255, 255, 255, 0.01);
    }}
    .ds-card-logo {{
      width: 36px;
      height: 36px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 16px;
      color: #fff;
    }}
    .btn-secondary {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 500;
      transition: background 0.2s;
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.1);
    }}
  </style>
</head>
<body>
  <!-- LEFT SIDEBAR -->
  <div class="sidebar" style="width: 250px; background: #111217; border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; padding: 20px 10px; gap: 20px;">
    <div class="logo-container" style="display: flex; align-items: center; gap: 12px; padding: 0 10px;">
      <div class="logo-icon" style="background: linear-gradient(135deg, #f99f1b, #f97316); color: #111217; width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px;">G</div>
      <h1 style="font-size: 18px; font-weight: 700; color: #fff;">Grafana</h1>
    </div>
    <div class="sidebar-menu" style="display: flex; flex-direction: column; gap: 6px;">
      <a href="/" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">📊</span> Dashboards
      </a>
      <a href="/datasources" class="menu-item active" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; color: #c084fc; background: rgba(249, 159, 27, 0.1); border: 1px solid rgba(249, 159, 27, 0.2); text-decoration: none;">
        <span class="menu-item-icon">🔌</span> Data Sources
      </a>
      <a href="http://localhost:8000/widget/resources.html" target="_blank" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">📋</span> Resource Eval UI
      </a>
      <a href="/explore" class="menu-item" style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); text-decoration: none; transition: background 0.2s;">
        <span class="menu-item-icon">🔍</span> Explore
      </a>
    </div>
    <div class="sidebar-footer" style="margin-top: auto; padding: 10px; font-size: 11px; color: var(--muted); border-top: 1px solid var(--border);">
      <div>Grafana v10.4.1</div>
      <div>Local Host Integration</div>
    </div>
  </div>

  <!-- MAIN CONTENT AREA -->
  <div class="content-area" style="flex: 1; display: flex; flex-direction: column; overflow-y: auto;">
    <header>
      <div class="logo-container">
        <div>
          <h1>Connections</h1>
          <div style="font-size:12px; color:var(--muted)">Home / Connections / Data sources</div>
        </div>
      </div>
      <div class="status-badge">
        <div class="pulse-dot"></div>
        Grafana Live (Port 3000)
      </div>
    </header>
    
    <main style="padding: 40px; max-width: 1200px; margin: 0; width: 100%;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
        <div>
          <h2 style="font-size: 22px; font-weight: 700; color: #fff;">Data sources</h2>
          <p style="font-size: 13px; color: var(--muted); margin-top: 4px;">Data sources configured for the DPI-LS observability system</p>
        </div>
        <button class="btn" style="padding: 10px 16px; font-size: 13px; font-weight: 600;">Add data source</button>
      </div>

      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="ds-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Endpoint / Path</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #e6522c, #ff7e47);">P</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">Prometheus <span style="background: rgba(249, 159, 27, 0.15); color: #f99f1b; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 6px; font-weight: bold;">default</span></div>
                    <div style="font-size: 11px; color: var(--muted);">Primary Infrastructure Metrics</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">Prometheus</td>
              <td style="font-family: monospace; font-size: 12px; color: #06b6d4;">http://localhost:9090</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Active (4 Targets UP)
                </div>
              </td>
              <td><button class="btn-secondary" onclick="window.open('http://localhost:9090')">Explore</button></td>
            </tr>
            
            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #7c3aed, #db2777);">🦅</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">Arize Phoenix</div>
                    <div style="font-size: 11px; color: var(--muted);">LLM Traces & Evaluations</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">OTLP Trace Engine</td>
              <td style="font-family: monospace; font-size: 12px; color: #06b6d4;">http://localhost:6006</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Active
                </div>
              </td>
              <td><button class="btn-secondary" onclick="window.open('http://localhost:6006')">Explore</button></td>
            </tr>

            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #2563eb, #3b82f6);">L</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">Langfuse</div>
                    <div style="font-size: 11px; color: var(--muted);">Agent Trace Explorer</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">Langfuse API</td>
              <td style="font-family: monospace; font-size: 12px; color: #06b6d4;">http://localhost:4000</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Connected
                </div>
              </td>
              <td><button class="btn-secondary" onclick="window.open('http://localhost:4000')">Explore</button></td>
            </tr>

            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #6246ea, #7f5af0);">O</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">OpenTelemetry</div>
                    <div style="font-size: 11px; color: var(--muted);">OTel Collector Ingest</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">OTLP gRPC</td>
              <td style="font-family: monospace; font-size: 12px; color: #06b6d4;">http://localhost:4317</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Receiving Spans
                </div>
              </td>
              <td><button class="btn-secondary" onclick="window.open('http://localhost:4317')">Explore</button></td>
            </tr>

            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #0ea5e9, #38bdf8);">🧪</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">MLflow</div>
                    <div style="font-size: 11px; color: var(--muted);">MLOps Experiment Tracking</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">MLflow Server</td>
              <td style="font-family: monospace; font-size: 12px; color: #06b6d4;">http://localhost:5000</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Active
                </div>
              </td>
              <td><button class="btn-secondary" onclick="window.open('http://localhost:5000')">Explore</button></td>
            </tr>

            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="ds-card-logo" style="background: linear-gradient(135deg, #4b5563, #6b7280);">💾</div>
                  <div>
                    <div style="font-weight: 600; font-size: 14px; color: #fff;">dpi_ls.db</div>
                    <div style="font-size: 11px; color: var(--muted);">Local SQLite Master Store</div>
                  </div>
                </div>
              </td>
              <td style="font-family: monospace; font-size: 12px; color: var(--muted);">SQLite Database</td>
              <td style="font-family: monospace; font-size: 11px; color: #f59e0b;">d:\\Projects\\widget\\widget\\dpi_ls.db</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px; color: var(--success); font-size: 12px; font-weight: 600;">
                  <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%;"></div>
                  Connected
                </div>
              </td>
              <td><button class="btn-secondary">Test Connection</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>
</body>
</html>
"""

def get_langfuse_html(data) -> str:
  total_tokens = data['input_tokens'] + data['output_tokens']
  val_score = data['validated'] / max(data['required'], 1)
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Langfuse - Agent Trace Explorer</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --bg: #090a0f;
      --panel-bg: #131520;
      --border: #222638;
      --accent: #2563eb;
      --glow-blue: 0 0 20px rgba(37, 99, 235, 0.2);
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #2563eb, #3b82f6);
    }}
    .trace-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .trace-item {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border);
      padding: 16px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      transition: background 0.2s;
    }}
    .trace-item:hover, .trace-item.active {{
      background: rgba(37, 99, 235, 0.1);
      border-color: var(--accent);
    }}
    .span-bar {{
      margin-left: 20px;
      border-left: 2px solid var(--border);
      padding-left: 16px;
      margin-top: 10px;
    }}
    .span-header {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      padding: 8px;
      background: rgba(255,255,255,0.01);
      border-radius: 6px;
      margin-bottom: 6px;
    }}
    .meta-tag {{
      background: rgba(255,255,255,0.05);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-family: monospace;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo-container">
      <div class="logo-icon">L</div>
      <div>
        <h1>Langfuse Tracing Dashboard</h1>
        <div style="font-size:12px; color:var(--muted)">LLM application Traces & Analytics</div>
      </div>
    </div>
    <div class="status-badge">
      <div class="pulse-dot"></div>
      Langfuse Running (Port 4000)
    </div>
  </header>
  <main>
    <div class="grid" style="grid-template-columns: 1fr 2fr; gap:24px">
      <div class="card" style="display:flex; flex-direction:column; gap:16px">
        <div class="card-title">Agent Traces</div>
        <div class="trace-list">
          <div class="trace-item active">
            <div>
              <div style="font-weight:600; font-size:14px">ChandraFinOpsRun</div>
              <div style="font-size:11px; color:var(--muted); margin-top:4px">chandra-finops • 250ms</div>
            </div>
            <div style="text-align:right">
              <div style="color:var(--success); font-weight:600">${data['model_cost']:.2f}</div>
              <div style="font-size:11px; color:var(--muted); margin-top:4px">{total_tokens // 1000}k tokens</div>
            </div>
          </div>
          
          <div class="trace-item">
            <div>
              <div style="font-weight:600; font-size:14px">QualityLLMEval</div>
              <div style="font-size:11px; color:var(--muted); margin-top:4px">evaluator-agent • 890ms</div>
            </div>
            <div style="text-align:right">
              <div style="color:var(--success); font-weight:600">$0.04</div>
              <div style="font-size:11px; color:var(--muted); margin-top:4px">4.2k tokens</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Trace Details: ChandraFinOpsRun</div>
        <div style="display:flex; flex-direction:column; gap:16px">
          <div style="display:flex; gap:12px; flex-wrap:wrap">
            <span class="meta-tag" style="color:#06b6d4">model: qwen.qwen3-next-80b-a3b</span>
            <span class="meta-tag">user: admin@intelligenzit.com</span>
            <span class="meta-tag">version: 0.3.0</span>
            <span class="meta-tag" style="color:var(--success)">compliance: SAFE</span>
          </div>

          <div style="background:rgba(0,0,0,0.2); border:1px solid var(--border); border-radius:12px; padding:20px">
            <div style="font-weight:700; font-size:14px; margin-bottom:8px">Input Prompt</div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--muted); background:#050608; padding:12px; border-radius:6px">
              "Run FinOps cost validation evaluation on model qwen."
            </div>
            
            <div style="font-weight:700; font-size:14px; margin-top:16px; margin-bottom:8px">Output Response</div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--success); background:#050608; padding:12px; border-radius:6px">
              "TCO: {data['total_cost']:.2f}, Validation Score: {val_score:.1f}, AI Cost: {data['model_cost']:.2f}, Human Cost: {data['human_cost']:.1f}"
            </div>
          </div>

          <div>
            <div style="font-weight:700; font-size:14px; margin-bottom:12px">Execution Spans</div>
            <div class="span-bar">
              <div class="span-header">
                <span style="font-weight:600">LLM Generation Span</span>
                <span style="color:#3b82f6">220ms • ${data['model_cost']:.2f}</span>
              </div>
              <div class="span-header" style="margin-left:20px">
                <span style="font-weight:600">api_call: bedrock:qwen.qwen3-next-80b-a3b</span>
                <span style="color:var(--muted)">{total_tokens:,} tokens</span>
              </div>
            </div>
            
            <div class="span-bar">
              <div class="span-header">
                <span style="font-weight:600">Policy Scan (Governance check)</span>
                <span style="color:#3b82f6">15ms • $0.00</span>
              </div>
            </div>

            <div class="span-bar">
              <div class="span-header">
                <span style="font-weight:600">Validation Check (Structure parser)</span>
                <span style="color:#3b82f6">5ms • $0.00</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</body>
</html>
"""

def get_otel_html(data) -> str:
  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>OpenTelemetry Collector Dashboard</title>
  <style>
    {SHARED_STYLES}
    :root {{
      --accent: #6246ea;
      --glow-blue: 0 0 20px rgba(98, 70, 234, 0.3);
    }}
    .logo-icon {{
      background: linear-gradient(135deg, #6246ea, #7f5af0);
    }}
    .pipeline-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      margin-bottom: 24px;
    }}
    .pipeline-card {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo-container">
      <div class="logo-icon">O</div>
      <div>
        <h1>OpenTelemetry Collector</h1>
        <div style="font-size:12px; color:var(--muted)">Telemetry Ingest & Routing Pipeline</div>
      </div>
    </div>
    <div class="status-badge">
      <div class="pulse-dot"></div>
      Collector Active (Port 4317)
    </div>
  </header>
  <main>
    <div class="pipeline-grid">
      <div class="pipeline-card" style="border-top: 4px solid var(--success)">
        <div style="display:flex; justify-content:space-between">
          <span style="font-weight:600">Traces Pipeline</span>
          <span style="color:var(--success)">Active</span>
        </div>
        <div style="font-size:24px; font-weight:700; margin-top:12px" id="traces-count">1,248 spans</div>
        <div style="font-size:11px; color:var(--muted); margin-top:4px">otlp/grpc -> jaeger / arize phoenix</div>
      </div>
      
      <div class="pipeline-card" style="border-top: 4px solid var(--success)">
        <div style="display:flex; justify-content:space-between">
          <span style="font-weight:600">Metrics Pipeline</span>
          <span style="color:var(--success)">Active</span>
        </div>
        <div style="font-size:24px; font-weight:700; margin-top:12px" id="metrics-count">10.4k metrics</div>
        <div style="font-size:11px; color:var(--muted); margin-top:4px">otlp/http -> prometheus</div>
      </div>

      <div class="pipeline-card" style="border-top: 4px solid var(--warning)">
        <div style="display:flex; justify-content:space-between">
          <span style="font-weight:600">Logs Pipeline</span>
          <span style="color:var(--warning)">Idle</span>
        </div>
        <div style="font-size:24px; font-weight:700; margin-top:12px">0 logs</div>
        <div style="font-size:11px; color:var(--muted); margin-top:4px">elasticapm / signoz routing</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Live Collector Logs</div>
      <div class="console" id="log-box" style="height:350px"></div>
    </div>
  </main>

  <script>
    const logBox = document.getElementById('log-box');
    let traces = 1248;
    let metrics = 10420;

    function addConsoleLine(type, msg) {{
      const time = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'console-line';
      div.innerHTML = `<span class="time">[${{time}}]</span><span class="${{type.toLowerCase()}}">${{type}}</span> ${{msg}}`;
      logBox.appendChild(div);
      logBox.scrollTop = logBox.scrollHeight;
    }}

    // Seed initial logs
    addConsoleLine("INFO", "OTel Collector initialized successfully.");
    addConsoleLine("INFO", "Receiver otlp/grpc listening on port 4317");
    addConsoleLine("INFO", "Receiver otlp/http listening on port 4318");
    addConsoleLine("INFO", "Pipeline traces started: receiver=otlp/grpc -> exporter=arize-phoenix");
    addConsoleLine("INFO", "Pipeline metrics started: receiver=otlp/http -> exporter=prometheus");

    // Dynamic log simulator
    setInterval(() => {{
      traces += 1;
      document.getElementById('traces-count').innerText = traces.toLocaleString() + " spans";
      addConsoleLine("INFO", "ExportTraceServiceRequest: 1 spans exported to Arize Phoenix (port 6006)");
    }}, 5000);

    setInterval(() => {{
      metrics += 15;
      document.getElementById('metrics-count').innerText = metrics.toLocaleString() + " metrics";
      addConsoleLine("INFO", "ExportMetricsServiceRequest: Scraped by Prometheus client (port 9090)");
    }}, 4000);
  </script>
</body>
</html>
"""

class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging request info to console to keep user terminal clean
        pass

    def do_GET(self):
        try:
            port = self.server.server_port
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            
            data = get_latest_data()
            
            if port == 9090:
                if self.path.startswith("/targets"):
                    self.wfile.write(get_prometheus_targets_html(data).encode("utf-8"))
                elif self.path.startswith("/service-discovery"):
                    self.wfile.write(get_prometheus_sd_html(data).encode("utf-8"))
                else:
                    self.wfile.write(get_prometheus_html(data).encode("utf-8"))
            elif port == 3000:
                if self.path.startswith("/datasources") or self.path.startswith("/connections"):
                    self.wfile.write(get_grafana_datasources_html(data).encode("utf-8"))
                else:
                    self.wfile.write(get_grafana_html(data).encode("utf-8"))
            elif port == 4000:
                self.wfile.write(get_langfuse_html(data).encode("utf-8"))
            else:
                self.wfile.write(b"Mock Server running successfully.")
        except (ConnectionAbortedError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        try:
            # Accept telemetry posts to simulate receivers
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"status": "success", "message": "Telemetry accepted"}')
        except (ConnectionAbortedError, ConnectionResetError, OSError):
            pass

def handle_otel_conn(conn):
    try:
        data = conn.recv(2048)
        if not data:
            conn.close()
            return
            
        if data.startswith(b"GET") or data.startswith(b"POST"):
            # HTTP request from browser
            latest_data = get_latest_data()
            response_body = get_otel_html(latest_data).encode("utf-8")
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: " + str(len(response_body)).encode() + b"\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Connection: close\r\n\r\n" + response_body
            )
            conn.sendall(response)
        else:
            # Swallow binary OTLP/gRPC connections and respond cleanly
            if b"POST /v1/traces" in data:
                resp = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                conn.sendall(resp)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

def run_otel_mock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", 4317))
        s.listen(10)
    except Exception as e:
        print(f"[ERROR] Failed to bind OTel mock on port 4317: {e}")
        return

    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=handle_otel_conn, args=(conn,), daemon=True).start()
        except Exception:
            break

def start_http_server(port: int):
    server = HTTPServer(("127.0.0.1", port), MockHTTPRequestHandler)
    print(f"  [OK] Mock service started on http://127.0.0.1:{port}")
    server.serve_forever()

def main():
    print("=========================================================")
    print("   Starting Mock Observability Dashboard Services")
    print("   (Prometheus, Grafana, Langfuse, OpenTelemetry)")
    print("=========================================================\n")

    # Start HTTP Servers
    for port in (9090, 3000, 4000):
        t = threading.Thread(target=start_http_server, args=(port,), daemon=True)
        t.start()

    # Start OTel TCP/HTTP Server on 4317
    otel_t = threading.Thread(target=run_otel_mock, daemon=True)
    otel_t.start()
    print("  [OK] Mock OpenTelemetry Collector started on port 4317")

    print("\nAll mock services are now running in the background.")
    print("Open the following URLs in your web browser:")
    print("  - Prometheus: http://localhost:9090")
    print("  - Grafana:    http://localhost:3000")
    print("  - Langfuse:   http://localhost:4000")
    print("  - OTel Dash:  http://localhost:4317\n")
    print("Press CTRL+C in this terminal to exit mock services.")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down mock services. Bye!")

if __name__ == "__main__":
    main()
