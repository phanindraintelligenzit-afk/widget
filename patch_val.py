import re

with open('dpi_ls/validation_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Just rip out Jaeger and Zipkin from allowed arrays and dicts
c = re.sub(r'"Jaeger",?\s*', '', c)
c = re.sub(r'"Zipkin",?\s*', '', c)

with open('dpi_ls/validation_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)

