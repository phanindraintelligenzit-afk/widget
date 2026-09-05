import re

with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('def push_quality_results_to_backend(ragas: dict, agentops: dict, host: str, port: int) -> None:', 'def push_quality_results_to_backend(deepeval: dict, ragas: dict, agentops: dict, host: str, port: int) -> None:')

new_push = '''
    post_data("push-deepeval", deepeval)
'''

c = c.replace('post_data("push-ragas", ragas)', new_push + '    post_data("push-ragas", ragas)')

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(c)

