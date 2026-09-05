import re

with open('tests/test_validation_resource_evaluation.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('assert len(resources) == 6', 'assert len(resources) == 4')

# Remove Jaeger and Zipkin from expected_names
c = re.sub(r'^\s*"Jaeger",\s*\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Zipkin",\s*\n', '', c, flags=re.MULTILINE)

with open('tests/test_validation_resource_evaluation.py', 'w', encoding='utf-8') as f:
    f.write(c)
