import re

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    c = f.read()

# Using regex to remove jaeger and zipkin services
c = re.sub(r'\n  jaeger:\n(?:    .*\n)*', '\n', c)
c = re.sub(r'\n  zipkin:\n(?:    .*\n)*', '\n', c)

with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.write(c)
