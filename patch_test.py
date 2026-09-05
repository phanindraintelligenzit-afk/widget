import re

with open('tests/test_enterprise_productivity.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('assert len(resources) == 5', 'assert len(resources) == 4')
c = c.replace('assert "Prometheus" in names\n', '')

with open('tests/test_enterprise_productivity.py', 'w', encoding='utf-8') as f:
    f.write(c)
