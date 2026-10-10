import re

def fix_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix agent_id extraction
    content = re.sub(r'agent_id\s*=\s*.*?split\("agent_id="\).*?\n', 'agent_id = "browser-e2e-agent"\n', content)
    content = re.sub(r'agent_id\s*=\s*url\.split.*?\[1\]', 'agent_id = "browser-e2e-agent"', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('tests/test_browser_e2e.py')
fix_file('tests/test_browser_ui.py')
