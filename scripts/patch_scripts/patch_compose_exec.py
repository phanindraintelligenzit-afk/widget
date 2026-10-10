import re

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    c = f.read()

# Match the phoenix block and remove it
c = re.sub(r'^\s*phoenix:\n(?:\s+.*\n)+', '', c, flags=re.MULTILINE)

with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.write(c)

