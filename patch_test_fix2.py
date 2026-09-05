with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('import sys\nimport os\n', '')
c = c.replace('from __future__ import annotations', 'from __future__ import annotations\nimport sys\nimport os\n')

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)
