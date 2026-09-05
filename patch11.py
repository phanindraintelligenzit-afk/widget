import re

# 1. Fix tests/test_cost_resource_evaluation.py
with open('tests/test_cost_resource_evaluation.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'^\s*"Prometheus",\s*\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Grafana",\s*\n', '', c, flags=re.MULTILINE)
with open('tests/test_cost_resource_evaluation.py', 'w', encoding='utf-8') as f:
    f.write(c)

# 2. Fix dpi_ls/risk_resource_evaluation_service.py syntax error
with open('dpi_ls/risk_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Since line 143 has a syntax error, let's restore it and then safely remove prometheus
# Wait, actually it's easier to run git checkout dpi_ls/risk_resource_evaluation_service.py and patch it safely.
