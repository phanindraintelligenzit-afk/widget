import re

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'class PrometheusAdapter\(EnterpriseProductivityAdapter\):[\s\S]*?    PrometheusAdapter\(\),\n', '', c)
c = c.replace('and Prometheus', '')

with open('dpi_ls/enterprise_productivity_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
