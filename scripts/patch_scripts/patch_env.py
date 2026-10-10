with open('.env.template', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('localhost:5432', 'postgres:5432  # Use postgres container name or AWS RDS endpoint')
c = c.replace('localhost:6379', 'redis:6379     # Use redis container name or AWS ElastiCache endpoint')
c = c.replace('localhost:3000', '127.0.0.1:3000 # Use external host URL for Langfuse if hosted elsewhere')

c += """
# OTel / Tracing Endpoints
JAEGER_ENDPOINT=http://otel-collector:14268
PROMETHEUS_URL=http://prometheus:9090

# Frontend Configuration
WIDGET_ALLOWED_ORIGINS=*
"""

with open('.env.template', 'w', encoding='utf-8') as f:
    f.write(c)
