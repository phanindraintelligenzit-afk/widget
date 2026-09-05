import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'"Prometheus",\s*', '', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
