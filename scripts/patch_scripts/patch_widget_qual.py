import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Remove LangSmith entries from map
c = re.sub(r'^\s*runtime_traces:\s*\{.*?"LangSmith".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*llm_evaluation:\s*\{.*?"LangSmith".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*hallucination_analysis:\s*\{.*?"LangSmith".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*prompt_evaluation:\s*\{.*?"LangSmith".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*context_evaluation:\s*\{.*?"LangSmith".*?\}\,?\n', '', c, flags=re.MULTILINE)

# Replace Confident AI with DeepEval
c = c.replace('"Confident AI"', '"DeepEval"')
c = c.replace('Confident AI (runtime telemetry)', 'DeepEval (runtime telemetry)')
c = c.replace('"LangSmith", ', '')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

