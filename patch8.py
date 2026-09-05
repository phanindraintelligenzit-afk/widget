import os
import glob
import re

for filepath in glob.glob('dpi_ls/*.py'):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean up empty colons
    content = re.sub(r'^\s*:\s*\[.*?\],?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*:\s*\[.*?\],?\r\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*:\s*grafana_keys,?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*:\s*prom_keys,?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*:\s*\[.*?\]\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*:\s*\d+,\n', '', content, flags=re.MULTILINE) # port map

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
