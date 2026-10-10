import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'^\s*elif r\.name == "Microsoft Presidio":\n(?:.*\n){1,2}', '', c, flags=re.MULTILINE)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)

