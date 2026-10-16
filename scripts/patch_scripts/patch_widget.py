import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix the broken Prometheus/Grafana object references
c = re.sub(r'src:\s*resource:\s*dec:', 'src: "Unknown", resource: "Unknown", dec:', c)
c = re.sub(r'if \(resourceName === \)', 'if (resourceName === "Unknown")', c)
c = re.sub(r'src:\s*resource:\s*dec:\s*0', 'src: "Unknown", resource: "Unknown", dec: 0', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

