with open('dpi_ls/governance_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'allowed = [' in line and 'Detect-Secrets' in line:
        line = line.replace(', "Detect-Secrets"', '').replace('"Detect-Secrets", ', '')
    elif '("Detect-Secrets"' in line:
        continue
    elif '"Detect-Secrets":' in line and not 'secrets_freq' in line and not 'secrets_incidents' in line:
        skip = True
        continue
    elif skip and '],' in line:
        skip = False
        continue
    elif skip:
        continue
    
    # Block for evaluate_all secrets
    if 'secrets_incidents = ' in line:
        continue
    if 'secrets_freq = ' in line:
        skip = True
        continue
    if skip and 'agent_executed=has_secrets' in line:
        skip = False
        continue
    if skip and ')' in line and 'save_governance_resource_evaluation' not in new_lines[-1]:
        skip = False
        continue

    new_lines.append(line)

with open('dpi_ls/governance_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
