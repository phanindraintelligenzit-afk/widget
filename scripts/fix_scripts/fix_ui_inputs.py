import re

for test_file in ['tests/test_browser_e2e.py', 'tests/test_browser_ui.py']:
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove department, scope, responsibilities
    content = re.sub(r'^\s*page\.fill\("#department".*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*page\.fill\("#scope".*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*page\.fill\("#responsibilities".*?\n', '', content, flags=re.MULTILINE)
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(content)

print("Fixed UI tests inputs")
