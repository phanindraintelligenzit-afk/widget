import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('def push_execution_results_to_backend(langfuse_res: dict, phoenix_res: dict, traceloop_res: dict, host: str, port: int) -> None:', 'def push_execution_results_to_backend(langfuse_res: dict, host: str, port: int) -> None:')

c = re.sub(r'^\s*if phoenix_res:\n(?:.*\n){1,6}', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*if traceloop_res:\n(?:.*\n){1,4}', '', c, flags=re.MULTILINE)

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

