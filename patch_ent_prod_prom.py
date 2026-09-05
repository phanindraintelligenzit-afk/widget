import re

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'class PrometheusAdapter\(EnterpriseProductivityAdapter\):[\s\S]*?        "Prometheus": "Queue Length",\n    }\n', '', c)
c = c.replace('PrometheusAdapter(),', '')
c = c.replace('adapter: str                        # "Langfuse" | "Prometheus"', 'adapter: str                        # "Langfuse"')

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
