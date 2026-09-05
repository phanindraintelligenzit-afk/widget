import os
import glob
import re

for filepath in glob.glob('widget/*.html') + glob.glob('widget/*.js'):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove from lists
    content = re.sub(r'"Prometheus",?\s*', '', content)
    content = re.sub(r"'Prometheus',?\s*", '', content)
    content = re.sub(r'"Grafana",?\s*', '', content)
    content = re.sub(r"'Grafana',?\s*", '', content)
    content = re.sub(r'"Grafana Tempo",?\s*', '', content)
    content = re.sub(r"'Grafana Tempo',?\s*", '', content)
    
    # Remove from maps/objects
    content = re.sub(r'Prometheus:\s*\{.*?\},\n', '', content, flags=re.DOTALL)
    content = re.sub(r'Grafana:\s*\{.*?\},\n', '', content, flags=re.DOTALL)
    content = re.sub(r"'Grafana Tempo':\s*\{.*?\},\n", '', content, flags=re.DOTALL)
    content = re.sub(r"'Prometheus':\s*\{.*?sdk:\s*'prometheus_client',\n\s*\},", '', content, flags=re.DOTALL)
    content = re.sub(r"'Grafana':\s*\{.*?sdk:\s*'grafana',\n\s*\},", '', content, flags=re.DOTALL)
    content = re.sub(r"'Grafana Tempo':\s*\{.*?\n\s*\},", '', content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
