import re

with open('dpi_ls/execution_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('"Phoenix", "Traceloop", ', '')
c = c.replace(', "Phoenix", "Traceloop"', '')
c = re.sub(r'^\s*"Phoenix":\s*\[.*?\],\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Traceloop":\s*\[.*?\],\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*\("Phoenix",.*?\),\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*\("Traceloop",.*?\),\n', '', c, flags=re.MULTILINE)

c = re.sub(r'^\s*"Phoenix":\s*\[[\s\S]*?^\s*\],\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Traceloop":\s*\[[\s\S]*?^\s*\],\n', '', c, flags=re.MULTILINE)

with open('dpi_ls/execution_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)

