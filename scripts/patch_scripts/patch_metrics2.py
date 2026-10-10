import sys

with open('api/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "# Mount Prometheus metrics endpoint" in line:
        new_lines.append("from prometheus_client import generate_latest, CONTENT_TYPE_LATEST\n")
        new_lines.append("from fastapi import Response\n")
        new_lines.append("@app.get('/metrics', include_in_schema=False)\n")
        new_lines.append("def metrics():\n")
        new_lines.append("    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)\n")
        new_lines.append("\n")

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Patched api/app.py with /metrics endpoint")
