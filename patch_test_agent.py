import re

with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('"/api/observations"', '"/ingest"')

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)

