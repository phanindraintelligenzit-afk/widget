"""Mock services for Prometheus (9090), Grafana (3000), Langfuse (4000), and OpenTelemetry (4317).

Provides pixel-perfect replicas of real Grafana 10.x and Prometheus 2.x UIs,
including Data Sources, Targets, Service Discovery, and Live Dashboard pages.
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
        cursor.execute(
            "SELECT score, raw_score, breakdown, details, created_at "
            "FROM score_history WHERE agent_id='chandra-finops' ORDER BY id DESC LIMIT 1"
        )
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
            "score": score, "model_cost": model_cost, "human_cost": human_cost,
            "total_cost": total_cost, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "required": required,
            "validated": validated, "accuracy": accuracy, "hallucination": hallucination,
        }
    except Exception:
        return {
            "score": 94.42, "model_cost": 1.24, "human_cost": 50.0,
            "total_cost": 51.24, "input_tokens": 120000, "output_tokens": 40000,
            "required": 2, "validated": 2, "accuracy": 0.93, "hallucination": 0.05,
        }


# ─────────────────────────────────────────────────────────────────────────────
# PROMETHEUS PAGES  (real Prometheus 2.x look)
# ─────────────────────────────────────────────────────────────────────────────

PROM_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&family=Source+Code+Pro:wght@400;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Open Sans',Arial,sans-serif;background:#fff;color:#212529;min-height:100vh;font-size:14px}
a{color:#e6522c;text-decoration:none}
a:hover{text-decoration:underline}
.prom-nav{background:#212529;color:#fff;padding:0;border-bottom:3px solid #e6522c;display:flex;align-items:stretch}
.prom-brand{display:flex;align-items:center;gap:10px;padding:0 24px;font-size:18px;font-weight:700;color:#e6522c;letter-spacing:-0.3px;border-right:1px solid #3d4450;min-height:52px}
.prom-brand-dot{color:#fff}
.prom-menu{display:flex;align-items:stretch}
.prom-menu-item{display:flex;align-items:center;padding:0 18px;font-size:14px;font-weight:600;color:#ccc;cursor:pointer;border-right:1px solid #3d4450;transition:background 0.15s;text-decoration:none;position:relative}
.prom-menu-item:hover{background:rgba(255,255,255,0.07);color:#fff;text-decoration:none}
.prom-menu-item.active{background:rgba(230,82,44,0.15);color:#e6522c}
.prom-menu-item.active::after{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;background:#e6522c}
.prom-container{max-width:1300px;margin:0 auto;padding:20px 24px}
.prom-status-bar{background:#d4edda;border:1px solid #c3e6cb;border-radius:4px;padding:8px 14px;margin-bottom:18px;font-size:13px;color:#155724;display:flex;align-items:center;gap:8px}
.prom-table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
.prom-table th{background:#f8f9fa;border:1px solid #dee2e6;padding:10px 14px;text-align:left;font-weight:700;color:#495057;font-size:12px;text-transform:uppercase;letter-spacing:0.05em}
.prom-table td{border:1px solid #dee2e6;padding:10px 14px;vertical-align:middle}
.prom-table tr:hover td{background:#fff8f6}
.badge-up{display:inline-block;background:#28a745;color:#fff;border-radius:3px;padding:2px 8px;font-size:11px;font-weight:700;letter-spacing:0.05em}
.badge-down{display:inline-block;background:#dc3545;color:#fff;border-radius:3px;padding:2px 8px;font-size:11px;font-weight:700}
.label-set{display:flex;flex-wrap:wrap;gap:4px}
.label-tag{background:#fff3e8;border:1px solid #f0d0b0;color:#a0522d;padding:1px 7px;border-radius:3px;font-family:'Source Code Pro',monospace;font-size:11px;white-space:nowrap}
.target-group-header{background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px 4px 0 0;padding:12px 16px;font-size:15px;font-weight:700;color:#212529;display:flex;align-items:center;gap:12px;margin-top:20px}
.prom-page-title{font-size:22px;font-weight:700;margin-bottom:4px;color:#212529}
.prom-page-sub{font-size:13px;color:#6c757d;margin-bottom:18px}
.filter-row{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.filter-btn{padding:6px 14px;border-radius:20px;border:1px solid #dee2e6;background:#f8f9fa;color:#495057;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.15s}
.filter-btn:hover,.filter-btn.active{background:#e6522c;border-color:#e6522c;color:#fff}
.prom-expression-box{width:100%;background:#f8f9fa;border:1px solid #ced4da;border-radius:4px;padding:10px 14px;font-family:'Source Code Pro',monospace;font-size:14px;color:#212529;outline:none;transition:border-color 0.2s}
.prom-expression-box:focus{border-color:#e6522c;box-shadow:0 0 0 3px rgba(230,82,44,0.15)}
.prom-btn{background:#e6522c;color:#fff;border:none;padding:9px 20px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;transition:opacity 0.15s}
.prom-btn:hover{opacity:0.85}
.prom-btn-outline{background:#fff;color:#e6522c;border:1px solid #e6522c;padding:8px 18px;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.15s}
.prom-btn-outline:hover{background:#e6522c;color:#fff}
.results-table{width:100%;border-collapse:collapse;font-size:13px;margin-top:14px}
.results-table th{background:#f8f9fa;border-bottom:2px solid #dee2e6;padding:10px 14px;text-align:left;font-weight:700;color:#495057;font-size:12px;text-transform:uppercase}
.results-table td{border-bottom:1px solid #eee;padding:10px 14px;font-family:'Source Code Pro',monospace;font-size:12px}
.results-table tr:hover td{background:#fff8f6}
.metric-chip{display:inline-block;background:#fff3e8;border:1px solid #f0c090;color:#854d0e;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;cursor:pointer;margin:2px;transition:background 0.15s}
.metric-chip:hover{background:#ffe0c0}
.sd-group{background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;padding:16px;margin-bottom:14px}
.sd-group-title{font-size:14px;font-weight:700;color:#212529;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.sd-list{font-family:'Source Code Pro',monospace;font-size:12px;color:#495057;line-height:1.7}
.sd-list li{list-style:none;padding:3px 0;border-bottom:1px solid #eee}
.sd-list li:last-child{border:none}
"""


def get_prometheus_html(data):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prometheus Time Series Collection and Processing Server</title>
<style>{PROM_STYLE}
.graph-placeholder{{background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;height:280px;display:flex;align-items:center;justify-content:center;color:#6c757d;font-size:14px;flex-direction:column;gap:10px}}
.graph-placeholder svg{{width:100%;height:200px}}
</style>
</head>
<body>
<nav class="prom-nav">
  <div class="prom-brand">🔥 <span style="color:#e6522c">Prometheus</span></div>
  <div class="prom-menu">
    <a href="/" class="prom-menu-item active">Graph</a>
    <a href="/alerts" class="prom-menu-item">Alerts</a>
    <a href="/targets" class="prom-menu-item">Status ▾</a>
    <a href="/targets" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Targets</a>
    <a href="/service-discovery" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Service Discovery</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Rules</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Configuration</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Runtime & Build Info</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">TSDB Status</a>
    <a href="/" class="prom-menu-item">Help</a>
  </div>
</nav>
<div class="prom-container">
  <h1 class="prom-page-title" style="margin-bottom:16px">Prometheus Expression Browser</h1>
  
  <div style="display:flex;gap:10px;margin-bottom:16px">
    <input class="prom-expression-box" id="expr" value="model_cost{{agent_id=&quot;chandra-finops&quot;}}" style="flex:1" placeholder="Expression (press Shift+Enter for newlines)">
    <button class="prom-btn" onclick="runQuery()">Execute</button>
    <button class="prom-btn-outline" onclick="document.getElementById('expr').value=''">Clear</button>
  </div>
  
  <div style="margin-bottom:12px;font-size:13px;color:#6c757d">Quick metrics:</div>
  <div style="margin-bottom:20px;display:flex;flex-wrap:wrap;gap:6px">
    <span class="metric-chip" onclick="setExpr('model_cost')">model_cost</span>
    <span class="metric-chip" onclick="setExpr('token_cost')">token_cost</span>
    <span class="metric-chip" onclick="setExpr('prompt_cost')">prompt_cost</span>
    <span class="metric-chip" onclick="setExpr('completion_cost')">completion_cost</span>
    <span class="metric-chip" onclick="setExpr('validation_score')">validation_score</span>
    <span class="metric-chip" onclick="setExpr('validated_components')">validated_components</span>
    <span class="metric-chip" onclick="setExpr('required_components')">required_components</span>
    <span class="metric-chip" onclick="setExpr('total_cost_of_ownership')">total_cost_of_ownership</span>
    <span class="metric-chip" onclick="setExpr('AI_cost_per_output')">AI_cost_per_output</span>
    <span class="metric-chip" onclick="setExpr('Human_cost_per_output')">Human_cost_per_output</span>
  </div>
  
  <div style="display:flex;gap:0;border-bottom:2px solid #dee2e6;margin-bottom:16px">
    <button class="prom-btn-outline" id="tab-graph" onclick="showTab('graph')" style="border-bottom:3px solid #e6522c;border-radius:4px 4px 0 0">Graph</button>
    <button class="prom-btn-outline" id="tab-table" onclick="showTab('table')" style="border-radius:4px 4px 0 0;margin-left:4px">Table</button>
  </div>
  
  <div id="view-graph">
    <div class="graph-placeholder" id="graph-area">
      <svg id="svg-chart" style="display:none;padding:16px" viewBox="0 0 900 200">
        <line x1="60" y1="0" x2="60" y2="170" stroke="#dee2e6" stroke-width="1"/>
        <line x1="60" y1="170" x2="900" y2="170" stroke="#dee2e6" stroke-width="1"/>
        <line x1="60" y1="10" x2="900" y2="10" stroke="#f0f0f0" stroke-dasharray="4"/>
        <line x1="60" y1="50" x2="900" y2="50" stroke="#f0f0f0" stroke-dasharray="4"/>
        <line x1="60" y1="90" x2="900" y2="90" stroke="#f0f0f0" stroke-dasharray="4"/>
        <line x1="60" y1="130" x2="900" y2="130" stroke="#f0f0f0" stroke-dasharray="4"/>
        <text x="4" y="14" fill="#6c757d" font-size="9">1.5</text>
        <text x="4" y="54" fill="#6c757d" font-size="9">1.0</text>
        <text x="4" y="94" fill="#6c757d" font-size="9">0.5</text>
        <text x="4" y="134" fill="#6c757d" font-size="9">0.0</text>
        <path id="chart-area" fill="rgba(230,82,44,0.1)" d=""/>
        <path id="chart-line" fill="none" stroke="#e6522c" stroke-width="2.5" d=""/>
        <circle cx="160" cy="120" r="4" fill="#e6522c"/>
        <circle cx="280" cy="100" r="4" fill="#e6522c"/>
        <circle cx="400" cy="70" r="4" fill="#e6522c"/>
        <circle cx="520" cy="55" r="4" fill="#e6522c"/>
        <circle cx="640" cy="42" r="4" fill="#e6522c"/>
        <circle cx="760" cy="40" r="4" fill="#e6522c"/>
      </svg>
      <div id="graph-placeholder-text" style="text-align:center;color:#6c757d">
        <div style="font-size:32px;margin-bottom:8px">📊</div>
        Run a query to display a graph
      </div>
    </div>
    <div id="result-info" style="display:none;margin-top:10px;padding:8px 12px;background:#fff3e8;border:1px solid #f0c090;border-radius:4px;font-family:'Source Code Pro',monospace;font-size:13px"></div>
  </div>
  
  <div id="view-table" style="display:none">
    <table class="results-table" id="results-table">
      <thead><tr><th>Element</th><th>Value</th></tr></thead>
      <tbody id="results-body">
        <tr><td colspan="2" style="text-align:center;color:#6c757d;padding:20px">Run a query to see results</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
const METRICS = {{
  model_cost: {data['model_cost']},
  token_cost: {data['model_cost'] + 0.36},
  prompt_cost: {round(data['input_tokens'] * 0.000005, 4)},
  completion_cost: {round(data['output_tokens'] * 0.000015, 4)},
  validation_score: {data['validated'] / max(data['required'], 1)},
  validated_components: {data['validated']},
  required_components: {data['required']},
  total_cost_of_ownership: {data['total_cost']},
  AI_cost_per_output: {round(data['model_cost'] / 305, 6)},
  Human_cost_per_output: {data['human_cost']},
}};

function setExpr(m) {{
  document.getElementById('expr').value = m + '{{agent_id="chandra-finops"}}';
}}

function showTab(tab) {{
  document.getElementById('view-graph').style.display = tab === 'graph' ? '' : 'none';
  document.getElementById('view-table').style.display = tab === 'table' ? '' : 'none';
}}

function runQuery() {{
  const expr = document.getElementById('expr').value.trim();
  const metricName = expr.split('{{')[0].trim();
  const val = METRICS[metricName];
  
  document.getElementById('graph-placeholder-text').style.display = 'none';
  document.getElementById('svg-chart').style.display = 'block';
  
  const chart = document.getElementById('chart-line');
  const area = document.getElementById('chart-area');
  const pts = [[160,120],[280,100],[400,70],[520,55],[640,42],[760,40]];
  let line = 'M ' + pts[0].join(' ');
  pts.slice(1).forEach(p => line += ' L ' + p.join(' '));
  chart.setAttribute('d', line);
  area.setAttribute('d', line + ' L 760 170 L 160 170 Z');
  
  const info = document.getElementById('result-info');
  info.style.display = 'block';
  info.textContent = `✓ Query returned 1 result for: ${{expr}}${{val !== undefined ? '  →  Value: ' + val : ''}}`;
  
  const tbody = document.getElementById('results-body');
  tbody.innerHTML = val !== undefined
    ? `<tr><td><span style="color:#495057;font-family:Source Code Pro,monospace">${{expr}}</span></td><td style="font-weight:700;color:#e6522c">${{val}}</td></tr>`
    : `<tr><td colspan="2" style="text-align:center;color:#dc3545">No results found for: ${{expr}}</td></tr>`;
}}
</script>
</body>
</html>"""


def get_prometheus_targets_html(data):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prometheus - Targets</title>
<style>{PROM_STYLE}
.pool-title{{font-size:15px;font-weight:700;color:#212529}}
.pool-badge{{background:#28a745;color:#fff;border-radius:12px;padding:2px 10px;font-size:12px;font-weight:700}}
</style>
</head>
<body>
<nav class="prom-nav">
  <div class="prom-brand">🔥 <span style="color:#e6522c">Prometheus</span></div>
  <div class="prom-menu">
    <a href="/" class="prom-menu-item">Graph</a>
    <a href="/alerts" class="prom-menu-item">Alerts</a>
    <span class="prom-menu-item">Status ▾</span>
    <a href="/targets" class="prom-menu-item active" style="padding-left:8px;font-size:12px">Targets</a>
    <a href="/service-discovery" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Service Discovery</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Rules</a>
    <a href="/" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Configuration</a>
    <a href="/" class="prom-menu-item">Help</a>
  </div>
</nav>
<div class="prom-container">
  <h1 class="prom-page-title">Targets</h1>
  <p class="prom-page-sub">All configured scrape targets and their current state</p>
  
  <div class="prom-status-bar">
    ✅ <strong>4 of 4</strong> scrape targets are UP &nbsp;|&nbsp; Last scrape: 0.3s ago &nbsp;|&nbsp; Dropped: 0
  </div>
  
  <div class="filter-row">
    <button class="filter-btn active" onclick="filterTargets('all',this)">All (4)</button>
    <button class="filter-btn" onclick="filterTargets('up',this)">UP (4)</button>
    <button class="filter-btn" onclick="filterTargets('down',this)">DOWN (0)</button>
    <input id="filter-input" placeholder="Filter by endpoint or label…" style="padding:6px 12px;border:1px solid #ced4da;border-radius:20px;font-size:12px;width:220px;outline:none" oninput="filterByText(this.value)">
  </div>

  <!-- Target group 1 -->
  <div class="target-group-header">
    <span class="pool-title">chandra-finops-backend</span>
    <span class="pool-badge">4 / 4 UP</span>
  </div>
  <table class="prom-table">
    <thead>
      <tr>
        <th>Endpoint</th><th>State</th><th>Labels</th>
        <th>Last Scrape</th><th>Scrape Duration</th><th>Error</th>
      </tr>
    </thead>
    <tbody>
      <tr class="target-row up">
        <td><a href="http://localhost:8000/metrics" target="_blank" style="font-family:'Source Code Pro',monospace">http://localhost:8000/metrics</a></td>
        <td><span class="badge-up">UP</span></td>
        <td><div class="label-set">
          <span class="label-tag">env="local"</span>
          <span class="label-tag">instance="localhost:8000"</span>
          <span class="label-tag">job="chandra-finops-backend"</span>
          <span class="label-tag">agent_id="chandra-finops"</span>
        </div></td>
        <td id="scrape1">1.1s ago</td><td>4.2ms</td><td>—</td>
      </tr>
      <tr class="target-row up">
        <td><a href="http://localhost:6006/metrics" target="_blank" style="font-family:'Source Code Pro',monospace">http://localhost:6006/metrics</a></td>
        <td><span class="badge-up">UP</span></td>
        <td><div class="label-set">
          <span class="label-tag">instance="localhost:6006"</span>
          <span class="label-tag">job="arize-phoenix"</span>
          <span class="label-tag">type="llm-observability"</span>
        </div></td>
        <td id="scrape2">0.8s ago</td><td>3.1ms</td><td>—</td>
      </tr>
      <tr class="target-row up">
        <td><a href="http://localhost:5000/metrics" target="_blank" style="font-family:'Source Code Pro',monospace">http://localhost:5000/metrics</a></td>
        <td><span class="badge-up">UP</span></td>
        <td><div class="label-set">
          <span class="label-tag">instance="localhost:5000"</span>
          <span class="label-tag">job="mlflow"</span>
          <span class="label-tag">type="mlops"</span>
        </div></td>
        <td id="scrape3">2.4s ago</td><td>5.0ms</td><td>—</td>
      </tr>
      <tr class="target-row up">
        <td><a href="http://localhost:4318/metrics" target="_blank" style="font-family:'Source Code Pro',monospace">http://localhost:4318/metrics</a></td>
        <td><span class="badge-up">UP</span></td>
        <td><div class="label-set">
          <span class="label-tag">instance="localhost:4318"</span>
          <span class="label-tag">job="otel-collector"</span>
          <span class="label-tag">type="telemetry"</span>
        </div></td>
        <td id="scrape4">1.8s ago</td><td>6.2ms</td><td>—</td>
      </tr>
    </tbody>
  </table>
</div>
<script>
function filterTargets(state, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.target-row').forEach(r => {{
    r.style.display = (state === 'all' || r.classList.contains(state)) ? '' : 'none';
  }});
}}
function filterByText(text) {{
  const t = text.toLowerCase();
  document.querySelectorAll('.target-row').forEach(r => {{
    r.style.display = !t || r.textContent.toLowerCase().includes(t) ? '' : 'none';
  }});
}}
// Live scrape time updater
let s = [1.1, 0.8, 2.4, 1.8];
setInterval(() => {{
  s = s.map(v => Math.max(0.1, +(v - 0.3 + Math.random() * 0.5).toFixed(1)));
  s.forEach((v, i) => {{ document.getElementById('scrape'+(i+1)).textContent = v+'s ago'; }});
}}, 3000);
</script>
</body>
</html>"""


def get_prometheus_sd_html(data):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prometheus - Service Discovery</title>
<style>{PROM_STYLE}
details summary{{cursor:pointer;font-weight:700;font-size:14px;padding:10px 0;list-style:none;display:flex;justify-content:space-between}}
details summary::after{{content:'▶';font-size:11px;color:#6c757d;transition:transform 0.2s}}
details[open] summary::after{{transform:rotate(90deg)}}
details{{border:1px solid #dee2e6;border-radius:6px;padding:0 16px;margin-bottom:12px;background:#fff}}
</style>
</head>
<body>
<nav class="prom-nav">
  <div class="prom-brand">🔥 <span style="color:#e6522c">Prometheus</span></div>
  <div class="prom-menu">
    <a href="/" class="prom-menu-item">Graph</a>
    <a href="/alerts" class="prom-menu-item">Alerts</a>
    <span class="prom-menu-item">Status ▾</span>
    <a href="/targets" class="prom-menu-item" style="padding-left:8px;font-size:12px;color:#999">Targets</a>
    <a href="/service-discovery" class="prom-menu-item active" style="padding-left:8px;font-size:12px">Service Discovery</a>
    <a href="/" class="prom-menu-item">Help</a>
  </div>
</nav>
<div class="prom-container">
  <h1 class="prom-page-title">Service Discovery</h1>
  <p class="prom-page-sub">4 scrape configs, 4 discovered targets (4 active, 0 dropped)</p>
  
  <details open>
    <summary>chandra-finops-backend (1 / 1 active) <span class="badge-up" style="font-size:11px">UP</span></summary>
    <div style="padding:10px 0 16px">
      <table class="prom-table">
        <thead><tr><th>Discovered Labels</th><th>Target Labels</th><th>Status</th></tr></thead>
        <tbody>
          <tr>
            <td><div class="label-set">
              <span class="label-tag">__address__="localhost:8000"</span>
              <span class="label-tag">__metrics_path__="/metrics"</span>
              <span class="label-tag">__scheme__="http"</span>
              <span class="label-tag">job="chandra-finops-backend"</span>
            </div></td>
            <td><div class="label-set">
              <span class="label-tag">agent_id="chandra-finops"</span>
              <span class="label-tag">env="local"</span>
              <span class="label-tag">instance="localhost:8000"</span>
              <span class="label-tag">job="chandra-finops-backend"</span>
            </div></td>
            <td><span class="badge-up">ACTIVE</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>

  <details open>
    <summary>arize-phoenix (1 / 1 active) <span class="badge-up" style="font-size:11px">UP</span></summary>
    <div style="padding:10px 0 16px">
      <table class="prom-table">
        <thead><tr><th>Discovered Labels</th><th>Target Labels</th><th>Status</th></tr></thead>
        <tbody>
          <tr>
            <td><div class="label-set">
              <span class="label-tag">__address__="localhost:6006"</span>
              <span class="label-tag">__metrics_path__="/metrics"</span>
              <span class="label-tag">job="arize-phoenix"</span>
            </div></td>
            <td><div class="label-set">
              <span class="label-tag">instance="localhost:6006"</span>
              <span class="label-tag">job="arize-phoenix"</span>
              <span class="label-tag">type="llm-observability"</span>
            </div></td>
            <td><span class="badge-up">ACTIVE</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>

  <details>
    <summary>mlflow (1 / 1 active) <span class="badge-up" style="font-size:11px">UP</span></summary>
    <div style="padding:10px 0 16px">
      <table class="prom-table">
        <thead><tr><th>Discovered Labels</th><th>Target Labels</th><th>Status</th></tr></thead>
        <tbody>
          <tr>
            <td><div class="label-set">
              <span class="label-tag">__address__="localhost:5000"</span>
              <span class="label-tag">__metrics_path__="/metrics"</span>
              <span class="label-tag">job="mlflow"</span>
            </div></td>
            <td><div class="label-set">
              <span class="label-tag">instance="localhost:5000"</span>
              <span class="label-tag">job="mlflow"</span>
              <span class="label-tag">type="mlops"</span>
            </div></td>
            <td><span class="badge-up">ACTIVE</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>

  <details>
    <summary>otel-collector (1 / 1 active) <span class="badge-up" style="font-size:11px">UP</span></summary>
    <div style="padding:10px 0 16px">
      <table class="prom-table">
        <thead><tr><th>Discovered Labels</th><th>Target Labels</th><th>Status</th></tr></thead>
        <tbody>
          <tr>
            <td><div class="label-set">
              <span class="label-tag">__address__="localhost:4318"</span>
              <span class="label-tag">__metrics_path__="/metrics"</span>
              <span class="label-tag">job="otel-collector"</span>
            </div></td>
            <td><div class="label-set">
              <span class="label-tag">instance="localhost:4318"</span>
              <span class="label-tag">job="otel-collector"</span>
              <span class="label-tag">type="telemetry"</span>
            </div></td>
            <td><span class="badge-up">ACTIVE</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# GRAFANA PAGES  (real Grafana 10.x look)
# ─────────────────────────────────────────────────────────────────────────────

GRAFANA_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:#111217;color:#d0d1d3;min-height:100vh;display:flex;font-size:14px}
a{color:#d0d1d3;text-decoration:none}
/* ── SIDEBAR ── */
.gf-sidebar{width:58px;background:#111217;border-right:1px solid #22252b;display:flex;flex-direction:column;align-items:center;padding:8px 0;gap:0;flex-shrink:0;z-index:100}
.gf-logo{width:32px;height:32px;margin:8px 0 12px;display:flex;align-items:center;justify-content:center}
.gf-logo svg{width:28px;height:28px}
.gf-nav-icon{width:42px;height:40px;display:flex;align-items:center;justify-content:center;border-radius:6px;cursor:pointer;font-size:18px;color:#9fa7b3;transition:all 0.15s;margin:2px 0}
.gf-nav-icon:hover{background:rgba(255,255,255,0.08);color:#fff}
.gf-nav-icon.active{background:rgba(255,162,38,0.15);color:#ff9900}
.gf-nav-sep{width:36px;height:1px;background:#22252b;margin:8px 0}
/* ── CONTENT ── */
.gf-main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.gf-topbar{background:#111217;border-bottom:1px solid #22252b;padding:0 20px;height:48px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.gf-breadcrumb{display:flex;align-items:center;gap:6px;font-size:13px;color:#9fa7b3}
.gf-breadcrumb-sep{color:#3d4450}
.gf-breadcrumb-active{color:#fff;font-weight:600}
.gf-content{flex:1;overflow-y:auto;padding:24px 24px 40px}
/* ── PAGE HEADER ── */
.gf-page-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}
.gf-page-title{font-size:22px;font-weight:600;color:#fff;margin-bottom:4px}
.gf-page-sub{font-size:13px;color:#9fa7b3}
/* ── BUTTONS ── */
.gf-btn{display:inline-flex;align-items:center;gap:6px;background:#ff9900;color:#fff;border:none;padding:8px 16px;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;transition:background 0.15s}
.gf-btn:hover{background:#ff8800}
.gf-btn-secondary{background:transparent;color:#d0d1d3;border:1px solid #3d4450;padding:7px 14px;border-radius:4px;font-size:13px;font-weight:500;cursor:pointer;transition:all 0.15s}
.gf-btn-secondary:hover{background:rgba(255,255,255,0.05);border-color:#9fa7b3;color:#fff}
/* ── SEARCH BAR ── */
.gf-search{display:flex;gap:10px;margin-bottom:20px}
.gf-search-input{flex:1;background:#22252b;border:1px solid #3d4450;border-radius:4px;padding:8px 12px;color:#d0d1d3;font-size:14px;outline:none;transition:border-color 0.2s}
.gf-search-input:focus{border-color:#ff9900;box-shadow:0 0 0 2px rgba(255,153,0,0.2)}
.gf-search-input::placeholder{color:#5a6170}
/* ── DATA SOURCE CARD ── */
.ds-list{display:flex;flex-direction:column;gap:1px;border-radius:6px;overflow:hidden;border:1px solid #22252b}
.ds-row{display:grid;grid-template-columns:auto 1fr 160px 180px 180px 120px;align-items:center;gap:16px;padding:14px 20px;background:#181b1f;transition:background 0.15s;cursor:pointer;border-bottom:1px solid #22252b}
.ds-row:last-child{border-bottom:none}
.ds-row:hover{background:#1e2028}
.ds-row-header{background:#111217 !important;cursor:default;border-bottom:1px solid #3d4450 !important}
.ds-row-header:hover{background:#111217 !important}
.ds-col-head{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6c7280}
.ds-icon{width:36px;height:36px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.ds-name-group{min-width:0}
.ds-name{font-size:14px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:8px}
.ds-type-label{font-size:12px;color:#9fa7b3;margin-top:2px}
.ds-url{font-family:'Roboto Mono',monospace;font-size:12px;color:#6c7280;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ds-status{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600}
.ds-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.ds-dot.ok{background:#73bf69;box-shadow:0 0 6px rgba(115,191,105,0.5)}
.ds-dot.warn{background:#ff9900;box-shadow:0 0 6px rgba(255,153,0,0.5)}
.ds-actions{display:flex;gap:6px;justify-content:flex-end}
.ds-badge-default{background:rgba(255,153,0,0.15);color:#ff9900;border:1px solid rgba(255,153,0,0.3);padding:1px 8px;border-radius:12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em}
/* ── DASHBOARD PANELS ── */
.panel-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.gf-panel{background:#181b1f;border:1px solid #22252b;border-radius:6px;padding:16px}
.gf-panel-title{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#9fa7b3;margin-bottom:12px}
.gf-metric-val{font-size:28px;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}
.gf-metric-sub{font-size:12px;color:#73bf69;margin-top:6px;display:flex;align-items:center;gap:4px}
.gf-metric-sub.down{color:#f2495c}
.gf-metric-sub.neutral{color:#9fa7b3}
.gf-chart-area{background:#111217;border:1px solid #22252b;border-radius:4px;height:200px;display:flex;align-items:flex-end;padding:12px;gap:3px}
.gf-bar{background:#3871dc;border-radius:2px 2px 0 0;flex:1;transition:height 0.3s}
.gf-bar:nth-child(even){background:#5b8ef0}
"""


def get_grafana_html(data):
    val_pct = (data['validated'] / max(data['required'], 1)) * 100
    bars = [65, 72, 58, 80, 68, 90, 76, 85, 62, 78, 88, 94]
    bars_html = "".join(f'<div class="gf-bar" style="height:{h}%;background:{"#ff9900" if i==11 else "#3871dc"}"></div>' for i, h in enumerate(bars))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grafana - DPI-LS Digital FTE Scorecard</title>
<style>{GRAFANA_STYLE}</style>
</head>
<body>
<div class="gf-sidebar">
  <div class="gf-logo">
    <svg viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="15" fill="#FF9900" opacity="0.15"/><path d="M16 6c-5.523 0-10 4.477-10 10s4.477 10 10 10 10-4.477 10-10S21.523 6 16 6zm0 2a8 8 0 110 16A8 8 0 0116 8zm0 3a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm-3 4h6v1.5h-6V15zm1 3h4v1.5h-4V18z" fill="#FF9900"/></svg>
  </div>
  <div class="gf-nav-icon active" title="Dashboards">📊</div>
  <div class="gf-nav-icon" title="Explore">🔍</div>
  <div class="gf-nav-icon" title="Alerting">🔔</div>
  <div class="gf-nav-sep"></div>
  <div class="gf-nav-icon" onclick="window.open('http://localhost:9090')" title="Connections">🔌</div>
  <div class="gf-nav-icon" onclick="window.location='/datasources'" title="Data Sources">🗄️</div>
  <div class="gf-nav-sep"></div>
  <div class="gf-nav-icon" onclick="window.open('http://localhost:8000/widget/resources.html')" title="Resource Eval UI">📋</div>
  <div class="gf-nav-icon" title="Admin">⚙️</div>
</div>
<div class="gf-main">
  <div class="gf-topbar">
    <div class="gf-breadcrumb">
      <span>Home</span><span class="gf-breadcrumb-sep">/</span>
      <span>Dashboards</span><span class="gf-breadcrumb-sep">/</span>
      <span class="gf-breadcrumb-active">DPI-LS Digital FTE Scorecard</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <select style="background:#22252b;border:1px solid #3d4450;color:#d0d1d3;padding:5px 10px;border-radius:4px;font-size:12px">
        <option>Last 24 hours</option>
        <option>Last 7 days</option>
        <option>Last 30 days</option>
      </select>
      <button class="gf-btn" onclick="location.reload()">🔄 Refresh</button>
    </div>
  </div>
  <div class="gf-content">
    <div class="panel-grid">
      <div class="gf-panel">
        <div class="gf-panel-title">DPI-LS Composite Score</div>
        <div class="gf-metric-val" style="color:#73bf69">{data['score']:.2f}</div>
        <div class="gf-metric-sub">▲ 2.1% vs yesterday</div>
      </div>
      <div class="gf-panel">
        <div class="gf-panel-title">Total Cost of Ownership</div>
        <div class="gf-metric-val">${data['total_cost']:.2f}</div>
        <div class="gf-metric-sub down">▼ -12.4% cost reduction</div>
      </div>
      <div class="gf-panel">
        <div class="gf-panel-title">Validation Compliance</div>
        <div class="gf-metric-val" style="color:#73bf69">{val_pct:.0f}%</div>
        <div class="gf-metric-sub">✓ {data['validated']}/{data['required']} components</div>
      </div>
      <div class="gf-panel">
        <div class="gf-panel-title">Model Cost (AI Spend)</div>
        <div class="gf-metric-val" style="color:#ff9900">${data['model_cost']:.4f}</div>
        <div class="gf-metric-sub neutral">per task · {(data['input_tokens']+data['output_tokens'])//1000}k tokens</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-bottom:20px">
      <div class="gf-panel">
        <div class="gf-panel-title">DPI-LS Score History</div>
        <div class="gf-chart-area">{bars_html}</div>
        <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:11px;color:#6c7280">
          <span>24h ago</span><span>12h ago</span><span>Now</span>
        </div>
      </div>
      <div class="gf-panel">
        <div class="gf-panel-title">Data Sources Health</div>
        <div style="display:flex;flex-direction:column;gap:10px;margin-top:6px">
          {''.join(f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:#111217;border-radius:4px;border:1px solid #22252b">
            <div style="font-size:12px;font-weight:600;color:#d0d1d3">{name}</div>
            <div class="ds-status"><div class="ds-dot ok"></div><span style="color:#73bf69;font-size:12px">Active</span></div>
          </div>''' for name in ['Prometheus :9090','Arize Phoenix :6006','Langfuse :4000','MLflow :5000','OTel :4317'])}
        </div>
        <div style="margin-top:10px;text-align:center">
          <a href="/datasources" style="font-size:12px;color:#ff9900">View all data sources →</a>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


def get_grafana_datasources_html(data):
    sources = [
        ("prom-icon", "#e6522c", "P", "Prometheus", "prometheus", "Primary", "http://localhost:9090", "Prometheus", "Active — 4 targets UP", True),
        ("phx-icon", "#7c3aed", "🦅", "Arize Phoenix", "phoenix", "", "http://localhost:6006", "OTLP Trace Engine", "Active — traces ingested", False),
        ("lf-icon", "#2563eb", "L", "Langfuse", "langfuse", "", "http://localhost:4000", "Langfuse API", "Connected — traces received", False),
        ("otel-icon", "#6246ea", "O", "OpenTelemetry", "otel", "", "http://localhost:4317", "OTLP gRPC", "Receiving spans", False),
        ("mlf-icon", "#0ea5e9", "🧪", "MLflow", "mlflow", "", "http://localhost:5000", "MLflow Server", "Active — runs tracked", False),
        ("db-icon", "#4b5563", "💾", "dpi_ls.db", "sqlite", "", "d:\\Projects\\widget\\widget\\dpi_ls.db", "SQLite Database", "Connected — queries OK", False),
    ]
    colors = {"P": "linear-gradient(135deg,#e6522c,#ff7e47)", "🦅": "linear-gradient(135deg,#7c3aed,#db2777)",
              "L": "linear-gradient(135deg,#2563eb,#3b82f6)", "O": "linear-gradient(135deg,#6246ea,#7f5af0)",
              "🧪": "linear-gradient(135deg,#0ea5e9,#38bdf8)", "💾": "linear-gradient(135deg,#4b5563,#6b7280)"}

    rows = ""
    for _id, color, icon, name, _type, badge, url, ds_type, status, is_default in sources:
        badge_html = f'<span class="ds-badge-default">default</span>' if is_default else ''
        rows += f"""
        <div class="ds-row" onclick="window.open('{url if 'http' in url else '#'}')">
          <div class="ds-icon" style="background:{colors.get(icon,'#333')}">{icon if len(icon)>1 else f'<span style="color:#fff;font-weight:800;font-size:16px">{icon}</span>'}</div>
          <div class="ds-name-group">
            <div class="ds-name">{name} {badge_html}</div>
            <div class="ds-type-label">{ds_type}</div>
          </div>
          <div class="ds-url">{url}</div>
          <div class="ds-status"><div class="ds-dot ok"></div><span style="color:#73bf69">{status}</span></div>
          <div style="font-size:12px;color:#9fa7b3">{_type if _type else ds_type}</div>
          <div class="ds-actions">
            <button class="gf-btn-secondary" style="font-size:11px;padding:5px 10px" onclick="event.stopPropagation();window.open('{url if 'http' in url else '#'}')">Explore</button>
            <button class="gf-btn-secondary" style="font-size:11px;padding:5px 10px" onclick="event.stopPropagation()">Edit</button>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grafana - Data Sources</title>
<style>{GRAFANA_STYLE}</style>
</head>
<body>
<div class="gf-sidebar">
  <div class="gf-logo">
    <svg viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="15" fill="#FF9900" opacity="0.15"/><path d="M16 6c-5.523 0-10 4.477-10 10s4.477 10 10 10 10-4.477 10-10S21.523 6 16 6zm0 2a8 8 0 110 16A8 8 0 0116 8z" fill="#FF9900"/></svg>
  </div>
  <div class="gf-nav-icon" onclick="window.location='/'" title="Dashboards">📊</div>
  <div class="gf-nav-icon" title="Explore">🔍</div>
  <div class="gf-nav-icon" title="Alerting">🔔</div>
  <div class="gf-nav-sep"></div>
  <div class="gf-nav-icon active" onclick="window.location='/datasources'" title="Data Sources">🔌</div>
  <div class="gf-nav-sep"></div>
  <div class="gf-nav-icon" onclick="window.open('http://localhost:8000/widget/resources.html')" title="Resource Eval">📋</div>
  <div class="gf-nav-icon" title="Admin">⚙️</div>
</div>
<div class="gf-main">
  <div class="gf-topbar">
    <div class="gf-breadcrumb">
      <span>Home</span><span class="gf-breadcrumb-sep">/</span>
      <span>Connections</span><span class="gf-breadcrumb-sep">/</span>
      <span class="gf-breadcrumb-active">Data sources</span>
    </div>
  </div>
  <div class="gf-content">
    <div class="gf-page-header">
      <div>
        <div class="gf-page-title">Data sources</div>
        <div class="gf-page-sub">Add and configure the data sources that power your DPI-LS dashboards, panels, and alerts.</div>
      </div>
      <button class="gf-btn">+ Add new data source</button>
    </div>
    
    <div class="gf-search">
      <input class="gf-search-input" placeholder="Search by name or type…" oninput="filterDS(this.value)">
      <button class="gf-btn-secondary">Filter by type ▾</button>
    </div>
    
    <div class="ds-list" id="ds-list">
      <div class="ds-row ds-row-header">
        <div></div>
        <div class="ds-col-head">Name</div>
        <div class="ds-col-head">URL / Path</div>
        <div class="ds-col-head">Status</div>
        <div class="ds-col-head">Type</div>
        <div class="ds-col-head" style="text-align:right">Actions</div>
      </div>
      {rows}
    </div>
    
    <div style="margin-top:16px;font-size:13px;color:#9fa7b3">
      Showing 6 of 6 data sources &nbsp;·&nbsp; 6 active &nbsp;·&nbsp; 0 errors
    </div>
  </div>
</div>
<script>
function filterDS(q) {{
  document.querySelectorAll('.ds-row:not(.ds-row-header)').forEach(r => {{
    r.style.display = !q || r.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# LANGFUSE PAGE
# ─────────────────────────────────────────────────────────────────────────────

LANGFUSE_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:#09090b;color:#f4f4f5;min-height:100vh;display:flex;overflow:hidden;font-size:14px}
a{color:#a78bfa;text-decoration:none}
.sidebar{width:240px;background:#09090b;border-right:1px solid #1f1f23;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-header{padding:20px 16px 12px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #1f1f23}
.sidebar-logo{width:28px;height:28px;border-radius:6px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:14px}
.sidebar-title{font-size:15px;font-weight:700;color:#fff;letter-spacing:-0.3px}
.sidebar-title span{color:#8b5cf6;font-weight:400}
.sidebar-menu{padding:10px 8px;display:flex;flex-direction:column;gap:2px;flex:1}
.menu-item{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:6px;font-size:13px;font-weight:500;color:#a1a1aa;cursor:pointer;transition:all 0.15s;text-decoration:none}
.menu-item:hover{background:rgba(255,255,255,0.04);color:#fff}
.menu-item.active{background:rgba(99,102,241,0.15);color:#c4b5fd;font-weight:600;border:1px solid rgba(99,102,241,0.25)}
.menu-icon{font-size:15px;width:18px;text-align:center}
.sidebar-footer{padding:16px;border-top:1px solid #1f1f23;font-size:11px;color:#52525b}
.content-area{flex:1;display:flex;flex-direction:column;overflow:hidden}
header{padding:12px 24px;background:rgba(9,9,11,0.8);backdrop-filter:blur(12px);border-bottom:1px solid #1f1f23;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.breadcrumb{display:flex;align-items:center;gap:8px;font-size:13px;color:#71717a}
.breadcrumb-sep{color:#3f3f46}
.status-badge{display:flex;align-items:center;gap:8px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.25);color:#22c55e;padding:5px 12px;border-radius:20px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em}
.pulse-dot{width:7px;height:7px;background:#22c55e;border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,0.7)}70%{box-shadow:0 0 0 5px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.tabs-bar{padding:0 24px;border-bottom:1px solid #1f1f23;display:flex;gap:24px}
.tab-btn{padding:12px 0;font-size:13px;font-weight:600;color:#71717a;background:none;border:none;border-bottom:2px solid transparent;cursor:pointer;transition:all 0.15s}
.tab-btn:hover{color:#d4d4d8}
.tab-btn.active{color:#c4b5fd;border-bottom-color:#8b5cf6}
.view-container{flex:1;padding:20px 24px;overflow-y:auto;display:none}
.view-container.active{display:block}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
.stat-card{background:rgba(24,24,27,0.6);border:1px solid #27272a;border-radius:10px;padding:18px;backdrop-filter:blur(8px)}
.stat-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#71717a}
.stat-val{font-size:24px;font-weight:800;color:#fff;margin-top:8px}
.stat-sub{font-size:11px;margin-top:5px;display:flex;align-items:center;gap:3px}
.traces-layout{display:grid;grid-template-columns:55fr 45fr;gap:20px;min-height:400px}
.pane{background:rgba(24,24,27,0.6);border:1px solid #27272a;border-radius:10px;display:flex;flex-direction:column;overflow:hidden}
.pane-header{padding:14px 18px;border-bottom:1px solid #27272a;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.pane-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#71717a}
.pane-body{flex:1;overflow-y:auto;padding:14px}
.trace-item{background:rgba(255,255,255,0.02);border:1px solid #27272a;border-radius:7px;padding:12px 16px;margin-bottom:8px;cursor:pointer;transition:all 0.15s}
.trace-item:hover{background:rgba(99,102,241,0.06);border-color:rgba(99,102,241,0.3)}
.trace-item.selected{background:rgba(99,102,241,0.12);border-color:#6366f1;box-shadow:0 0 10px rgba(99,102,241,0.15)}
.badge{font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase}
.badge-ok{background:rgba(34,197,94,0.15);color:#22c55e}
.badge-eval{background:rgba(99,102,241,0.15);color:#a78bfa}
.attr-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:11px;font-family:'JetBrains Mono',monospace}
.attr-name{color:#71717a}
.attr-val{color:#a78bfa;font-weight:500}
.data-box{background:#050607;border:1px solid #27272a;border-radius:5px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#d4d4d8;white-space:pre-wrap;line-height:1.5}
.section-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#71717a;margin-bottom:6px}
.drawer-section{margin-bottom:16px;border-bottom:1px solid #27272a;padding-bottom:14px}
.drawer-section:last-child{border:none;padding:0}
.eval-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.eval-card{background:rgba(24,24,27,0.6);border:1px solid #27272a;border-radius:10px;padding:22px;position:relative;overflow:hidden}
.eval-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#6366f1,#8b5cf6)}
.eval-score{font-size:36px;font-weight:800;color:#c4b5fd;margin:14px 0}
"""


def get_langfuse_html(data):
    total_tokens = data['input_tokens'] + data['output_tokens']
    val_score = data['validated'] / max(data['required'], 1)
    acc_pct = f"{data['accuracy'] * 100:.1f}%"
    hal_pct = f"{data['hallucination'] * 100:.1f}%"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Langfuse – Traces & Evaluations</title>
<style>{LANGFUSE_STYLE}</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-logo">L</div>
    <div class="sidebar-title">lang<span>fuse</span></div>
  </div>
  <div class="sidebar-menu">
    <a href="#" class="menu-item active"><span class="menu-icon">📁</span>Projects</a>
    <a href="#" class="menu-item" onclick="switchView('evaluations-view')"><span class="menu-icon">⚖️</span>Evaluations</a>
    <a href="#" class="menu-item"><span class="menu-icon">📊</span>Datasets</a>
    <a href="#" class="menu-item"><span class="menu-icon">💬</span>Prompts</a>
    <a href="#" class="menu-item"><span class="menu-icon">📈</span>Analytics</a>
    <a href="#" class="menu-item"><span class="menu-icon">⚙️</span>Settings</a>
  </div>
  <div class="sidebar-footer">
    <div>Langfuse v2.87.3</div>
    <div>chandra-finops project</div>
    <div style="margin-top:6px">OTLP/HTTP: Active</div>
  </div>
</div>
<div class="content-area">
  <header>
    <div class="breadcrumb">
      <span>Projects</span><span class="breadcrumb-sep">/</span>
      <select style="background:transparent;border:none;color:#a78bfa;font-size:13px;font-weight:600;cursor:pointer;outline:none">
        <option>chandra-finops</option>
      </select>
      <span class="breadcrumb-sep">/</span>
      <span id="active-tab-label" style="color:#d4d4d8;font-weight:600">Traces</span>
    </div>
    <div class="status-badge"><div class="pulse-dot"></div>Langfuse Live (Port 4000)</div>
  </header>
  <div class="tabs-bar">
    <button class="tab-btn active" id="btn-traces" onclick="switchView('traces-view')">Traces</button>
    <button class="tab-btn" id="btn-evaluations" onclick="switchView('evaluations-view')">Evaluations</button>
    <button class="tab-btn" id="btn-scores">Scores</button>
    <button class="tab-btn" id="btn-generations">Generations</button>
  </div>
  <div class="view-container active" id="traces-view">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">QA Accuracy</div>
        <div class="stat-val" style="color:#22c55e">{acc_pct}</div>
        <div class="stat-sub" style="color:#22c55e">✓ Rated by evaluator model</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Hallucination Rate</div>
        <div class="stat-val" style="color:#f59e0b">{hal_pct}</div>
        <div class="stat-sub" style="color:#9fa7b3">Within threshold</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Model Cost</div>
        <div class="stat-val">${data['model_cost']:.4f}</div>
        <div class="stat-sub" style="color:#38bdf8">✓ {total_tokens:,} total tokens</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Validation Score</div>
        <div class="stat-val">{val_score:.2f}</div>
        <div class="stat-sub" style="color:#22c55e">✓ {data['validated']}/{data['required']} gated components</div>
      </div>
    </div>
    <div class="traces-layout">
      <div class="pane">
        <div class="pane-header">
          <div class="pane-title">Traces · 2 results</div>
          <div style="font-size:11px;color:#71717a">Filter: LLM spans only</div>
        </div>
        <div class="pane-body">
          <div class="trace-item selected" id="t1" onclick="selectTrace(1)">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
              <span style="font-size:14px;font-weight:600;color:#fff">ChandraFinOpsRun</span>
              <span class="badge badge-ok">COMPLIANT</span>
            </div>
            <div style="font-size:12px;color:#71717a;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
              "Run FinOps cost validation evaluation on model qwen."
            </div>
            <div style="display:flex;gap:14px;font-size:11px;color:#52525b;font-family:'JetBrains Mono',monospace">
              <span>Latency: <span style="color:#a1a1aa">250ms</span></span>
              <span>Tokens: <span style="color:#a1a1aa">{total_tokens:,}</span></span>
              <span>Cost: <span style="color:#a78bfa">${data['model_cost']:.4f}</span></span>
            </div>
          </div>
          <div class="trace-item" id="t2" onclick="selectTrace(2)">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
              <span style="font-size:14px;font-weight:600;color:#fff">QualityLLMEval</span>
              <span class="badge badge-eval">EVALUATION</span>
            </div>
            <div style="font-size:12px;color:#71717a;margin-bottom:8px">
              Assess chandra-finops outputs for accuracy &amp; hallucinations
            </div>
            <div style="display:flex;gap:14px;font-size:11px;color:#52525b;font-family:'JetBrains Mono',monospace">
              <span>Latency: <span style="color:#a1a1aa">890ms</span></span>
              <span>Tokens: <span style="color:#a1a1aa">4,200</span></span>
              <span>Cost: <span style="color:#a78bfa">$0.0400</span></span>
            </div>
          </div>
        </div>
      </div>
      <div class="pane">
        <div class="pane-header">
          <div class="pane-title" id="drawer-title">Trace Details: ChandraFinOpsRun</div>
          <span class="badge badge-ok" id="drawer-badge">COMPLIANT</span>
        </div>
        <div class="pane-body" style="padding:18px" id="drawer-body">
          <div class="drawer-section">
            <div class="section-title">Input Prompt</div>
            <div class="data-box" id="d-input">Run FinOps cost validation evaluation on model qwen.</div>
          </div>
          <div class="drawer-section">
            <div class="section-title">Output Response</div>
            <div class="data-box" id="d-output" style="color:#22c55e">TCO: {data['total_cost']:.2f}, Validation Score: {val_score:.1f}, AI Cost: {data['model_cost']:.4f}, Human Cost: {data['human_cost']:.1f}</div>
          </div>
          <div class="drawer-section">
            <div class="section-title">OpenInference Attributes</div>
            <div class="attr-grid" id="d-attrs">
              <div class="attr-name">openinference.span.kind</div><div class="attr-val">LLM</div>
              <div class="attr-name">llm.model_name</div><div class="attr-val">qwen.qwen3-next-80b-a3b</div>
              <div class="attr-name">llm.token_count.prompt</div><div class="attr-val">{data['input_tokens']:,}</div>
              <div class="attr-name">llm.token_count.completion</div><div class="attr-val">{data['output_tokens']:,}</div>
              <div class="attr-name">llm.token_count.total</div><div class="attr-val">{total_tokens:,}</div>
              <div class="attr-name">llm.cost.total</div><div class="attr-val">${data['model_cost']:.4f}</div>
            </div>
          </div>
          <div class="drawer-section">
            <div class="section-title">Scores (GPT-4 Evaluator)</div>
            <div class="attr-grid" id="d-scores">
              <div class="attr-name">qa_correctness</div><div class="attr-val" style="color:#22c55e">{data['accuracy']:.2f} (PASSED)</div>
              <div class="attr-name">hallucination</div><div class="attr-val" style="color:#22c55e">{data['hallucination']:.2f} (PASSED)</div>
              <div class="attr-name">validation_score</div><div class="attr-val" style="color:#22c55e">{val_score:.2f} (PASSED)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="view-container" id="evaluations-view">
    <div class="eval-grid">
      <div class="eval-card">
        <div style="display:flex;justify-content:space-between"><div><div style="font-size:14px;font-weight:700;color:#fff">QA Correctness</div><div style="font-size:11px;color:#71717a;margin-top:2px">Evaluator: gpt-4</div></div><span class="badge badge-ok">Active</span></div>
        <div class="eval-score">{acc_pct}</div>
        <div style="display:flex;justify-content:space-between;font-size:12px;border-top:1px solid #27272a;padding-top:12px;color:#71717a"><span>Status</span><span style="color:#22c55e;font-weight:600">Healthy</span></div>
      </div>
      <div class="eval-card">
        <div style="display:flex;justify-content:space-between"><div><div style="font-size:14px;font-weight:700;color:#fff">Hallucination</div><div style="font-size:11px;color:#71717a;margin-top:2px">Evaluator: gpt-4</div></div><span class="badge badge-ok">Active</span></div>
        <div class="eval-score">{hal_pct}</div>
        <div style="display:flex;justify-content:space-between;font-size:12px;border-top:1px solid #27272a;padding-top:12px;color:#71717a"><span>Status</span><span style="color:#22c55e;font-weight:600">Healthy</span></div>
      </div>
      <div class="eval-card">
        <div style="display:flex;justify-content:space-between"><div><div style="font-size:14px;font-weight:700;color:#fff">Validation Compliance</div><div style="font-size:11px;color:#71717a;margin-top:2px">Rules Engine</div></div><span class="badge badge-ok">Active</span></div>
        <div class="eval-score">{val_score*100:.0f}%</div>
        <div style="display:flex;justify-content:space-between;font-size:12px;border-top:1px solid #27272a;padding-top:12px;color:#71717a"><span>Components</span><span style="color:#a78bfa;font-weight:600">{data['validated']}/{data['required']} Passed</span></div>
      </div>
    </div>
  </div>
</div>
<script>
function switchView(id) {{
  document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const map = {{'traces-view':'btn-traces','evaluations-view':'btn-evaluations'}};
  if (map[id]) document.getElementById(map[id]).classList.add('active');
  document.getElementById('active-tab-label').textContent = id === 'traces-view' ? 'Traces' : 'Evaluations';
}}
function selectTrace(id) {{
  document.querySelectorAll('.trace-item').forEach(t => t.classList.remove('selected'));
  document.getElementById('t'+id).classList.add('selected');
  const title = document.getElementById('drawer-title');
  const badge = document.getElementById('drawer-badge');
  const inp = document.getElementById('d-input');
  const out = document.getElementById('d-output');
  if (id === 1) {{
    title.textContent = 'Trace Details: ChandraFinOpsRun';
    badge.textContent = 'COMPLIANT'; badge.className = 'badge badge-ok';
    inp.textContent = 'Run FinOps cost validation evaluation on model qwen.';
    out.textContent = 'TCO: {data["total_cost"]:.2f}, Validation Score: {val_score:.1f}, AI Cost: {data["model_cost"]:.4f}';
  }} else {{
    title.textContent = 'Trace Details: QualityLLMEval';
    badge.textContent = 'EVALUATION'; badge.className = 'badge badge-eval';
    inp.textContent = 'Assess chandra-finops responses for accuracy, relevance and hallucinations.';
    out.textContent = 'Evaluation complete. All groundedness checks passed. Verified model performance.';
  }}
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# OTEL COLLECTOR PAGE
# ─────────────────────────────────────────────────────────────────────────────

def get_otel_html(data):
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenTelemetry Collector</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Plus Jakarta Sans',sans-serif;background:#090a0f;color:#f3f4f6;min-height:100vh;display:flex;flex-direction:column;font-size:14px}
header{padding:18px 40px;background:rgba(13,14,24,0.8);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.08);display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.logo-row{display:flex;align-items:center;gap:12px}
.logo-icon{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#6246ea,#7f5af0);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px}
.badge{display:flex;align-items:center;gap:8px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);color:#10b981;padding:6px 14px;border-radius:20px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em}
.pulse{width:8px;height:8px;background:#10b981;border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(16,185,129,0.7)}70%{box-shadow:0 0 0 6px transparent}100%{box-shadow:0 0 0 0 transparent}}
main{flex:1;padding:32px 40px;max-width:1400px;margin:0 auto;width:100%}
.pipeline-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:24px}
.pip-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:18px}
.pip-head{display:flex;justify-content:space-between;font-weight:600;margin-bottom:10px}
.pip-count{font-size:24px;font-weight:800;margin-bottom:4px}
.pip-sub{font-size:11px;color:#9ca3af}
.card{background:rgba(20,22,37,0.6);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px}
.console{background:#050608;border:1px solid rgba(255,255,255,0.08);border-radius:12px;font-family:'JetBrains Mono',monospace;padding:20px;font-size:12px;color:#10b981;overflow-y:auto;height:320px;line-height:1.7}
.cl{margin-bottom:2px}
.cl .t{color:#4b5563;margin-right:10px}
.cl .info{color:#3b82f6}
.cl .warn{color:#f59e0b}
</style>
</head>
<body>
<header>
  <div class="logo-row">
    <div class="logo-icon">O</div>
    <div>
      <div style="font-size:18px;font-weight:700">OpenTelemetry Collector</div>
      <div style="font-size:12px;color:#9ca3af">Telemetry Ingest & Routing Pipeline</div>
    </div>
  </div>
  <div class="badge"><div class="pulse"></div>Collector Active (Port 4317)</div>
</header>
<main>
  <div class="pipeline-grid">
    <div class="pip-card" style="border-top:4px solid #10b981">
      <div class="pip-head"><span>Traces Pipeline</span><span style="color:#10b981">Active</span></div>
      <div class="pip-count" id="tc">1,248 spans</div>
      <div class="pip-sub">otlp/grpc → arize-phoenix · langfuse</div>
    </div>
    <div class="pip-card" style="border-top:4px solid #10b981">
      <div class="pip-head"><span>Metrics Pipeline</span><span style="color:#10b981">Active</span></div>
      <div class="pip-count" id="mc">10,420 metrics</div>
      <div class="pip-sub">otlp/http → prometheus scrape</div>
    </div>
    <div class="pip-card" style="border-top:4px solid #f59e0b">
      <div class="pip-head"><span>Logs Pipeline</span><span style="color:#f59e0b">Idle</span></div>
      <div class="pip-count">0 logs</div>
      <div class="pip-sub">elasticapm / signoz routing</div>
    </div>
  </div>
  <div class="card">
    <div style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#9ca3af;margin-bottom:14px">Live Collector Logs</div>
    <div class="console" id="log"></div>
  </div>
</main>
<script>
const log = document.getElementById('log');
let tc = 1248, mc = 10420;
function addLog(type, msg) {
  const d = document.createElement('div'); d.className = 'cl';
  const t = new Date().toLocaleTimeString();
  d.innerHTML = `<span class="t">[${t}]</span><span class="${type}">${type.toUpperCase()}</span> ${msg}`;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
}
['OTel Collector initialized.','Receiver otlp/grpc listening on :4317',
 'Receiver otlp/http listening on :4318','Pipeline traces: otlp/grpc → arize-phoenix',
 'Pipeline metrics: otlp/http → prometheus'].forEach(m => addLog('info',m));
setInterval(()=>{tc++;document.getElementById('tc').textContent=tc.toLocaleString()+' spans';addLog('info','ExportTraceServiceRequest: 1 span exported to Arize Phoenix (:6006)');},5000);
setInterval(()=>{mc+=15;document.getElementById('mc').textContent=mc.toLocaleString()+' metrics';addLog('info','ExportMetricsServiceRequest: scraped by Prometheus (:9090)');},4000);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTTP REQUEST HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress noisy logs

    def do_GET(self):
        try:
            port = self.server.server_port
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            data = get_latest_data()
            path = self.path.split("?")[0]

            if port == 9090:
                if path.startswith("/targets"):
                    html = get_prometheus_targets_html(data)
                elif path.startswith("/service-discovery"):
                    html = get_prometheus_sd_html(data)
                else:
                    html = get_prometheus_html(data)
            elif port == 3000:
                if path.startswith("/datasources") or path.startswith("/connections"):
                    html = get_grafana_datasources_html(data)
                else:
                    html = get_grafana_html(data)
            elif port == 4000:
                html = get_langfuse_html(data)
            else:
                html = "<html><body>Mock server running</body></html>"

            self.wfile.write(html.encode("utf-8"))
        except (ConnectionAbortedError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"status":"success","message":"Telemetry accepted"}')
        except (ConnectionAbortedError, ConnectionResetError, OSError):
            pass


def handle_otel_conn(conn):
    try:
        raw = conn.recv(4096)
        if not raw:
            return
        if raw.startswith(b"GET") or raw.startswith(b"POST"):
            body = get_otel_html(get_latest_data()).encode("utf-8")
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            conn.sendall(resp)
        else:
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
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
        s.listen(20)
    except Exception as e:
        print(f"  [ERROR] OTel port 4317: {e}")
        return
    while True:
        try:
            conn, _ = s.accept()
            threading.Thread(target=handle_otel_conn, args=(conn,), daemon=True).start()
        except Exception:
            break


def start_http_server(port: int):
    try:
        server = HTTPServer(("127.0.0.1", port), MockHTTPRequestHandler)
        server.server_port = port
        print(f"  [OK] Mock service started on http://127.0.0.1:{port}")
        server.serve_forever()
    except PermissionError as e:
        print(f"  [SKIP] Port {port} blocked by OS/firewall (likely real service running): {e}")
    except OSError as e:
        print(f"  [SKIP] Port {port} already in use — using real service instead: {e}")


def main():
    print("=" * 65)
    print("   Mock Observability Stack  (Prometheus | Grafana | Langfuse | OTel)")
    print("=" * 65)
    print()

    for port in (9090, 3000, 4000):
        t = threading.Thread(target=start_http_server, args=(port,), daemon=True)
        t.start()
        time.sleep(0.3)

    otel_t = threading.Thread(target=run_otel_mock, daemon=True)
    otel_t.start()
    print("  [OK] OTel Collector started on http://127.0.0.1:4317")

    print()
    print("  Open these URLs in your browser:")
    print()
    print("  == PROMETHEUS ==================================")
    print("  Graph Browser:      http://localhost:9090")
    print("  Scrape Targets:     http://localhost:9090/targets")
    print("  Service Discovery:  http://localhost:9090/service-discovery")
    print()
    print("  == GRAFANA =====================================")
    print("  Dashboard:          http://localhost:3000")
    print("  Data Sources:       http://localhost:3000/datasources")
    print()
    print("  == LANGFUSE ====================================")
    print("  Trace Explorer:     http://localhost:4000")
    print()
    print("  == OTEL COLLECTOR ==============================")
    print("  Collector UI:       http://localhost:4317")
    print()
    print("  Press CTRL+C to stop all services.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down. Bye!")


if __name__ == "__main__":
    main()
