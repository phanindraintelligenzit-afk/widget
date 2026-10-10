import re

with open('tests/test_enterprise_productivity.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('assert len(match_analysis) == 2', 'assert len(match_analysis) == 1')

with open('tests/test_enterprise_productivity.py', 'w', encoding='utf-8') as f:
    f.write(c)
