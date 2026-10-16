import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace push_quality_results_to_backend signature
c = c.replace('def push_quality_results_to_backend(langsmith: dict, ragas: dict, agentops: dict, host: str, port: int) -> None:', 'def push_quality_results_to_backend(ragas: dict, agentops: dict, host: str, port: int) -> None:')
c = re.sub(r'^\s*post_data\("push-langsmith", langsmith\)\n', '', c, flags=re.MULTILINE)

# Remove run_langsmith from integrations.py
c = re.sub(r'def run_langsmith\(\) -> dict:[\s\S]*?return results\n', '', c)

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

