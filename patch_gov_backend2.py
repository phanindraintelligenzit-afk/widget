import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = r'\s*\+ \(presidio\.get\("PII Entities Detected"\) or 0\)'
c = re.sub(target, '', c)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

