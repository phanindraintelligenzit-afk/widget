import os
import re
import yaml

# Read .env
env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip()

# Read docker-compose.yml
with open('docker-compose.yml', 'r') as f:
    dc = yaml.safe_load(f)

services = dc.get('services', {})

# Read app.py
with open('api/app.py', 'r', encoding='utf-8') as f:
    app_py = f.read()

# Analyze mismatches and missing endpoints
print("DOCKER-COMPOSE SERVICES:")
for name, config in services.items():
    ports = config.get('ports', [])
    print(f" - {name}: {ports}")

print("\nENV VARS URLS/ENDPOINTS:")
for k, v in env_vars.items():
    if 'URL' in k or 'ENDPOINT' in k or 'HOST' in k:
        print(f" - {k}: {v}")

print("\nAPP.PY URL FETCHES:")
matches = re.findall(r'os\.environ\.get\([\'\"](.*?)[\'\"]', app_py)
for m in sorted(list(set(matches))):
    print(f" - {m}")
