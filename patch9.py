import re

def safe_replace(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Prune lists:
    c = re.sub(r'"Prometheus",?', '', c)
    c = re.sub(r'"Grafana",?', '', c)
    c = re.sub(r'\s*,\s*\]', ']', c)
    
    # We will just comment out the entire lines in dicts/lists to be safe.
    lines = c.split('\n')
    new_lines = []
    for line in lines:
        if 'Prometheus' in line or 'Grafana' in line or 'prom_keys' in line or 'grafana_keys' in line:
            # check if it is part of a list initialization like ("Grafana", ...)
            if line.strip().startswith('("Grafana"') or line.strip().startswith('("Prometheus"'):
                continue
            if 'Grafana' in line and '{"url"' in line: continue
            if 'Prometheus' in line and '{"url"' in line: continue
            if line.strip().startswith('"Grafana"'): continue
            if line.strip().startswith('"Prometheus"'): continue
            if 'grafana_keys =' in line or 'prom_keys =' in line: continue
        new_lines.append(line)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

safe_replace('dpi_ls/cost_resource_evaluation_service.py')
