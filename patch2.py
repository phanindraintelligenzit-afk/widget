import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    app = f.read()

app = re.sub(r'from \.metrics_exporter import export_cost_metrics\n', '', app)
app = re.sub(r'                        export_cost_metrics\(session\)\n', '', app)

# Remove the endpoint entirely
app = re.sub(r'@app\.post\("/api/metrics/export"\).*?return \{\n.*?\}\n', '', app, flags=re.DOTALL)
app = re.sub(r'from prometheus_client import make_asgi_app\n', '', app)
app = re.sub(r'app\.mount\("/metrics", make_asgi_app\(\)\)\n', '', app)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(app)
