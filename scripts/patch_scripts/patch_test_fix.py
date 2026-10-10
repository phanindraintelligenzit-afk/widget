with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('import sys, os\n    sys.stdout', 'sys.stdout')
c = 'import sys\nimport os\n' + c

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)
