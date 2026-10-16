import os
import glob
import re

for filepath in glob.glob('dpi_ls/*.py'):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to remove Prometheus and Grafana elements from allowed/resources/maps
    # e.g., allowed = ["Langfuse", "Prometheus", "Grafana", "OpenLIT", "OpenCost"] -> remove them
    content = re.sub(r'"Prometheus",?\s*', '', content)
    content = re.sub(r"'Prometheus',?\s*", '', content)
    content = re.sub(r'"Grafana",?\s*', '', content)
    content = re.sub(r"'Grafana',?\s*", '', content)
    content = re.sub(r'"Grafana Tempo",?\s*', '', content)
    content = re.sub(r"'Grafana Tempo',?\s*", '', content)

    # Let's clean up orphaned commas in lists if any. But be careful.
    
    # Specific removals for dictionaries:
    content = re.sub(r'Prometheus:\s*\{.*?\},', '', content, flags=re.DOTALL)
    content = re.sub(r'Grafana:\s*\{.*?\},', '', content, flags=re.DOTALL)
    content = re.sub(r'Grafana Tempo:\s*\{.*?\},', '', content, flags=re.DOTALL)

    content = re.sub(r'\("Prometheus".*?\),', '', content)
    content = re.sub(r'\("Grafana".*?\),', '', content)
    content = re.sub(r'\("Grafana Tempo".*?\),', '', content)
    
    content = re.sub(r'# Prometheus / Grafana metrics still use the backend runtime score logic as before', '', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
