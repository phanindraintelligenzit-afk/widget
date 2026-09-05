import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix the broken Prometheus/Grafana object references
c = re.sub(r'resource:\s*dec:', 'resource: "Unknown", dec:', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

