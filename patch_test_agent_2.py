import re

with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'obs\["productivity"\].*?\n.*?obs\["quality"\].*?\n.*?obs\["executions"\].*?\n', '', c)

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)
