import os
import re

files = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

for f_path in files:
    if not os.path.exists(f_path): continue
    with open(f_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Lock body scroll
    content = re.sub(r'(body\s*{[^}]*display:\s*flex;\s*)min-height:\s*100vh;', r'\1height: 100vh; overflow: hidden;', content)
    
    # Just to be safe, if we missed it
    if 'overflow: hidden;' not in content.split('.sidebar')[0]:
        content = re.sub(r'(body\s*{)', r'\1 overflow: hidden; height: 100vh; ', content)

    with open(f_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Body locked!")
