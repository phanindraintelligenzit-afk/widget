file_path = 'api/app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find the start of the endpoint
start_idx = content.find('@app.post("/api/agents/{agent_id}/score/preview")')
if start_idx != -1:
    # Find the end of the endpoint (before the next @app.post)
    end_idx = content.find('@app.post("/api/agents/{agent_id}/run_telemetry")', start_idx)
    if end_idx != -1:
        # Comment out everything in between
        endpoint_code = content[start_idx:end_idx]
        commented_code = '\n'.join(['# ' + line for line in endpoint_code.split('\n')])
        content = content[:start_idx] + commented_code + content[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
