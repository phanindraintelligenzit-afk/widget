import re

with open('dpi_ls/quality_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('(True, True, True, True),\n', '')
c = c.replace('real_values = {"LangSmith": {}, "Ragas": {}, "AgentOps": {}}', 'real_values = {"Ragas": {}, "AgentOps": {}, "DeepEval": {}}')
c = c.replace('LangSmith, Ragas, and AgentOps', 'Ragas, AgentOps, and DeepEval')

with open('dpi_ls/quality_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
