import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace in PROD_M
c = c.replace('"Langfuse", "Prometheus", "Grafana Tempo", "Apache SkyWalking"', '"Langfuse", "Grafana Tempo", "Apache SkyWalking"')

# Replace in getCat
c = c.replace('["Falco", "Sentry", "Prometheus"]', '["Falco", "Sentry"]')

# Replace in knownResources
c = c.replace('"Langfuse", "Phoenix", "Traceloop", "Prometheus", "Grafana",', '"Langfuse", "Grafana",')

# Replace Backend Engine and Prometheus with Langfuse in metricsMap for productivity
c = re.sub(r'src:\s*"Prometheus",\s*resource:\s*"Prometheus"', 'src: "Workflow Layer", resource: "Workflow Layer"', c)
c = re.sub(r'src:\s*"Backend Engine",\s*resource:\s*"Backend Engine"', 'src: "Workflow Layer", resource: "Workflow Layer"', c)
c = re.sub(r'src:\s*"Productivity Service",\s*resource:\s*"Backend Engine"', 'src: "Productivity Service", resource: "Workflow Layer"', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
