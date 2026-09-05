import sys
with open('api/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('active_resources = {\"OpenTelemetry\", \"Apache SkyWalking\", \"Langfuse\", \"Prometheus\"}', 'active_resources = {\"OpenTelemetry\", \"Apache SkyWalking\", \"Langfuse\"}')
content = content.replace('active_resources = {\"Langfuse\"}', 'active_resources = {\"Langfuse\", \"OpenTelemetry\", \"Jaeger\"}')

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
