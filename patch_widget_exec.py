import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'^\s*Total_Attempts:\s*\{.*?"Phoenix".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*Successful_Attempts:\s*\{.*?"Phoenix".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*execution_status:\s*\{.*?"Phoenix".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*Execution_Score:\s*\{.*?"Phoenix".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*workflow_execution:\s*\{.*?"Traceloop".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*workflow_status:\s*\{.*?"Traceloop".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*root_span:\s*\{.*?"Traceloop".*?\}\,?\n', '', c, flags=re.MULTILINE)

c = c.replace('"Phoenix", "Traceloop", ', '')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

