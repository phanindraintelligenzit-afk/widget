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

NEW_CSS = """    .sidebar-link {
        display: block;
        padding: 14px 32px;
        color: var(--text);
        text-decoration: none;
        font-weight: 500;
        font-size: 16px;
        transition: all 0.2s;
        border-left: 4px solid transparent;
      }
      .sidebar-link:hover {
        background: rgba(255,255,255,0.05);
        border-left: 4px solid var(--accent);
      }
      .sidebar-link.active {
        font-weight: 700;
        background: rgba(255,255,255,0.1);
        border-left: 4px solid var(--accent);
      }"""

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Use regex to find and replace the block from .sidebar-link { to } for active
    pattern = re.compile(r'\.sidebar-link\s*\{.*?\.sidebar-link\.active\s*\{.*?\}', re.DOTALL)
    
    if pattern.search(content):
        content = pattern.sub(NEW_CSS.strip(), content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Updated CSS in {file_path}")

print("Sidebar CSS hover/active fix complete!")
