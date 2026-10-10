import re

# Clean .env files
for filepath in ['.env', '.env.example', '.env.template']:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            c = f.read()
        
        c = re.sub(r'^.*JAEGER.*$\n', '', c, flags=re.MULTILINE|re.IGNORECASE)
        c = re.sub(r'^.*ZIPKIN.*$\n', '', c, flags=re.MULTILINE|re.IGNORECASE)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(c)
    except FileNotFoundError:
        pass

# Clean docker-compose.yml
with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if line.strip() == 'jaeger:' or line.strip() == 'zipkin:':
        skip = True
        continue
    # If we are skipping, we skip until the next top-level service (no indentation)
    if skip and line.strip() != '' and not line.startswith(' ') and not line.startswith('\t'):
        skip = False
    
    # Wait, in docker-compose, services are indented by 2 spaces.
    if skip and not line.startswith('  '):
        # Not possible since they are under services: but let's check indent.
        pass
        
    # Better approach for docker compose:
