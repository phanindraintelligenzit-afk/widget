file_path = 'api/app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We need to uncomment the endpoint. Let's find it.
lines = content.split('\n')
for i, line in enumerate(lines):
    if line.startswith('# @app.post("/api/agents/{agent_id}/score/preview")'):
        # Found the start of the commented block
        j = i
        while j < len(lines) and lines[j].startswith('#'):
            lines[j] = lines[j][2:] # Remove '# '
            j += 1
        break

content = '\n'.join(lines)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
