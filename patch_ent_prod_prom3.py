import re

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'class PrometheusAdapter\(EnterpriseProductivityAdapter\):[\s\S]*?class OpenTelemetryAdapter', 'class OpenTelemetryAdapter', c)
c = c.replace('PrometheusAdapter(),\n', '')
c = c.replace('"Prometheus":', '# "Prometheus":')

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
