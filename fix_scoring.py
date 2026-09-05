import re
with open('api/scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'\"Microsoft Presidio\": presidio,\s*\"Detect-Secrets\": secrets,\s*',
    '',
    content
)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
