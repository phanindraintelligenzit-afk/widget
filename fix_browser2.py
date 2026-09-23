import re

def fix_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix alice -> admin
    content = content.replace('page.fill("#username", "alice")', 'page.fill("#username", "admin")')
    content = content.replace('page.fill("#password", "pass")', 'page.fill("#password", "admin123")')
    
    # Fix agent_name -> agent_id in ui tests
    content = content.replace('page.fill("#agent_name", "Browser E2E Agent")', 'page.fill("#agent_id", "Browser E2E Agent")')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('tests/test_browser_e2e.py')
fix_file('tests/test_browser_ui.py')
