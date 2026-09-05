import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('def push_enterprise_quality_results_to_backend(deepeval_res: dict, trulens_res: dict, host: str, port: int) -> None:', 'def push_enterprise_quality_results_to_backend(deepeval_res: dict, host: str, port: int) -> None:')

# Remove trulens code inside push_enterprise_quality_results_to_backend
c = re.sub(r'^\s*if trulens_res:\n(?:.*\n){1,10}', '', c, flags=re.MULTILINE)

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

