import re

with open('dpi_ls/quality_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace Confident AI with DeepEval
c = c.replace('"Confident AI"', '"DeepEval"')

# Remove LangSmith
c = c.replace('"LangSmith", ', '')
c = c.replace('("LangSmith", True, True, True, True),', '')
c = re.sub(r'^\s*"LangSmith":\s*\[.*?\],\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"LangSmith":\s*\{.*?\}\,?\n?', '', c, flags=re.MULTILINE)

with open('dpi_ls/quality_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)

