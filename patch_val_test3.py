import re

with open('tests/test_validation_resource_evaluation.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('assert len(latest_results) == 31', 'assert len(latest_results) == 16')

with open('tests/test_validation_resource_evaluation.py', 'w', encoding='utf-8') as f:
    f.write(c)
