import os
import re

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_top_header = '<div style="margin-right: auto;"><span id="login-time-display"'
    new_top_header = '<div style="margin-right: auto; display: flex; align-items: center; gap: 20px;">\n          <h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>\n          <span id="login-time-display"'
    
    if 'margin: 0; font-size: 22px;' not in content:
        content = content.replace(old_top_header, new_top_header)

    content = content.replace('<h1>DPI-LS (Digital Performance Index - Life Science)</h1>', '')
    content = content.replace('<h1 style="margin-top: 0; margin-bottom: 5px;">DPI-LS (Digital Performance Index - Life Science)</h1>\n    ', '')
    content = content.replace('<h1 style="margin-bottom: 5px;">DPI-LS (Digital Performance Index - Life Science)</h1>\n  ', '')

    if 'demo.html' in file_path:
        pattern = re.compile(r'<strong>DPI-LS</strong>.*?<br>\s*<br>', re.DOTALL)
        content = pattern.sub('', content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        print(f"Updated header and text in {file_path}")

print("Header layout update complete!")
