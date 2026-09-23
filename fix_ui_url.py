import re

for test_file in ['tests/test_browser_e2e.py', 'tests/test_browser_ui.py']:
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('agent-config.html?agent_id=*', 'demo.html*')
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(content)
