import re
import os

def patch_app():
    with open('api/app.py', 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Remove SMTP
    pattern = re.compile(r'import os, smtplib.*?print\(f\"\\n\[DPI-LS SMTP\] ERROR: Failed to send Score email: \{e\}\"\)', re.DOTALL)
    text, count = pattern.subn('', text)
    print(f'Removed SMTP: {count}')
    
    with open('api/app.py', 'w', encoding='utf-8') as f:
        f.write(text)

def patch_poster():
    with open('dpi_ls/poster.py', 'r', encoding='utf-8') as f:
        text = f.read()
    text = text.replace('_DEFAULT_TIMEOUT_S = 10.0', '_DEFAULT_TIMEOUT_S = 60.0')
    with open('dpi_ls/poster.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched poster.py')

def patch_test_agent():
    with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
        text = f.read()
    
    old_str = """    if is_mock:
        from unittest.mock import patch
        import litellm"""
        
    new_str = """    if is_mock:
        from unittest.mock import patch
        import litellm
        
        async def mock_fetch(*args, **kwargs): return {'status': 'mocked_costs'}
        fetcher.fetch_costs_summary = mock_fetch"""
        
    if old_str in text:
        text = text.replace(old_str, new_str)
        print('Patched test_agent.py')
    else:
        print('Could not find string in test_agent.py')
        
    with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
        f.write(text)

patch_app()
patch_poster()
patch_test_agent()
