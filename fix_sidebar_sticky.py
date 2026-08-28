import os
import re

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html',
    'widget/logout.html'
]

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will replace .sidebar { with .sidebar { position: sticky; top: 0; height: 100vh; overflow-y: auto;
    # Ensure we don't apply it multiple times
    if 'position: sticky;' not in content and '.sidebar {' in content:
        content = content.replace(
            '.sidebar {\n      width: 260px;',
            '.sidebar {\n      width: 260px;\n      position: sticky;\n      top: 0;\n      height: 100vh;\n      overflow-y: auto;'
        )
        # Handle variations in spacing
        content = content.replace(
            '.sidebar {\n        width: 260px;',
            '.sidebar {\n        width: 260px;\n        position: sticky;\n        top: 0;\n        height: 100vh;\n        overflow-y: auto;'
        )
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Fixed sticky sidebar in {file_path}")

print("Sidebar sticky fix complete!")
