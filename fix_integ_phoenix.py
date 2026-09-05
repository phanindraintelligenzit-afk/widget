import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'^\s*post_data\("push-phoenix".*?\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*post_data\("push-traceloop".*?\)\n', '', c, flags=re.MULTILINE)

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

