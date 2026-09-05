import re

with open('dpi_ls/quality_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(', "TruLens"', '')
c = re.sub(r'^\s*"TruLens":\s*\[.*?\],?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*\("TruLens",.*?\),\n', '', c, flags=re.MULTILINE)

with open('dpi_ls/quality_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)

