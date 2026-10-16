import re

for test_file in ['tests/test_browser_e2e.py', 'tests/test_browser_ui.py']:
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace #agent_name with #agent_id
    content = content.replace('page.fill("#agent_name"', 'page.fill("#agent_id"')
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(content)

print("Fixed UI tests")
