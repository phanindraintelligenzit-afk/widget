import sys
with open('dpi_ls/risk_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if '_OWNED_METRICS = {' in line:
        new_lines.append(line)
        skip = True
        continue
    if skip and '        "Falco": [' in line:
        skip = False
    
    if not skip:
        new_lines.append(line)

with open('dpi_ls/risk_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
