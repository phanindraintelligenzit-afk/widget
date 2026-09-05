import re
import os
import shutil

# 1. Update docker-compose.yml
print('Updating docker-compose.yml')
with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    dc_content = f.read()

dc_content = re.sub(r'  prometheus:.*?restart: unless-stopped\n\n', '', dc_content, flags=re.DOTALL)
dc_content = re.sub(r'  grafana:.*?restart: unless-stopped\n\n', '', dc_content, flags=re.DOTALL)
with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.write(dc_content)


# 2. Clean .env files
print('Updating .env files')
for env_file in ['.env', '.env.example', '.env.template', 'aws_deployment_guide.md']:
    if not os.path.exists(env_file): continue
    with open(env_file, 'r', encoding='utf-8') as f:
        env_content = f.read()
    env_content = re.sub(r'# Grafana Configuration\nGRAFANA_URL=.*?\n', '', env_content)
    env_content = re.sub(r'# Prometheus Configuration\nPROMETHEUS_URL=.*?\n', '', env_content)
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)


# 3. Clean api/app.py
print('Updating api/app.py')
with open('api/app.py', 'r', encoding='utf-8') as f:
    app = f.read()

app = re.sub(r'    prom_url = os\.environ\.get\("PROMETHEUS_URL"\)\n', '', app)
app = re.sub(r'    graf_url = os\.environ\.get\("GRAFANA_URL"\)\n', '', app)
app = re.sub(r'    logger\.info\(f"Prometheus:\\n\{prom_url or \'MISSING\'\}\\n"\)\n', '', app)
app = re.sub(r'    logger\.info\(f"Grafana:\\n\{graf_url or \'MISSING\'\}"\)\n', '', app)
app = re.sub(r'    if not prom_url:\n        missing\.append\("PROMETHEUS_URL"\)\n', '', app)
app = re.sub(r'    if not graf_url:\n        missing\.append\("GRAFANA_URL"\)\n', '', app)

app = re.sub(r'            from api\.metrics_exporter import export_cost_metrics_to_prometheus\n            .*?logger\.info\("Started Prometheus metrics export task"\)\n', '', app, flags=re.DOTALL)
app = re.sub(r'            if export_task:\n                export_task\.cancel\(\)\n                logger\.info\("Stopped Prometheus metrics export task"\)\n', '', app, flags=re.DOTALL)

app = re.sub(r'from prometheus_client import make_asgi_app\n\n# Mount Prometheus metrics endpoint\nmetrics_app = make_asgi_app\(\)\napp\.mount\("/metrics", metrics_app\)\n', '', app)

app = re.sub(r'        elif r\.name == "Prometheus":\n            url = os\.environ\.get\("PROMETHEUS_URL", "#"\)\n', '', app)
app = re.sub(r'"Prometheus", "Grafana", ', '', app)

app = re.sub(r'    prometheus_url = os\.environ\.get\("PROMETHEUS_URL", "http://localhost:9090"\)\n', '', app)
app = re.sub(r'    grafana_url = os\.environ\.get\("GRAFANA_URL", "http://localhost:3000"\)\n', '', app)
app = re.sub(r'        "Prometheus": {"url": prometheus_url, "online": _is_reachable_global\(prometheus_url\)},\n', '', app)
app = re.sub(r'        "Grafana":    {"url": grafana_url,    "online": _is_reachable_global\(grafana_url\)},\n', '', app)

app = re.sub(r'        "Grafana Tempo":     {"url": tempo_ui_url,      "online": _is_reachable_global\(tempo_url\)},\n', '', app)

app = re.sub(r'    "Prometheus",\n', '', app)
app = re.sub(r'    "Grafana",\n', '', app)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(app)


# 4. Clean api/bootstrap.py
print('Updating api/bootstrap.py')
with open('api/bootstrap.py', 'r', encoding='utf-8') as f:
    boot = f.read()
boot = re.sub(r'            # Pre-populate Prometheus Gauges with the latest scores from DB on startup\n            from api\.scoring import update_prometheus_metrics\n', '', boot)
boot = re.sub(r'                    update_prometheus_metrics\(agent_row\.id, rating\)\n', '', boot)
with open('api/bootstrap.py', 'w', encoding='utf-8') as f:
    f.write(boot)


# 5. Clean api/scoring.py
print('Updating api/scoring.py')
with open('api/scoring.py', 'r', encoding='utf-8') as f:
    scor = f.read()

# Remove the function def
scor = re.sub(r'def update_prometheus_metrics\(agent_id: str, rating: Rating\) -> None:\n(?:    .*?(\n|$))+?(?=\ndef |\Z)', '', scor)

# Remove the calls
scor = re.sub(r'    update_prometheus_metrics\(.*?rating\)\n', '', scor)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(scor)

# 6. Delete api/metrics_exporter.py
print('Deleting api/metrics_exporter.py')
if os.path.exists('api/metrics_exporter.py'):
    os.remove('api/metrics_exporter.py')

print('All patches applied.')
