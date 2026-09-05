import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('def push_execution_results_to_backend(langfuse: dict, phoenix: dict, traceloop: dict, host: str, port: int) -> None:', 'def push_execution_results_to_backend(langfuse: dict, host: str, port: int) -> None:')

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

