import re
with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('collector.finalize()', 'import sys, os\n    sys.stdout = open(os.devnull, "w")\n    try:\n        collector.finalize()\n    finally:\n        sys.stdout = sys.__stdout__')

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)
