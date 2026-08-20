import glob
import re

for f in glob.glob('d:/DPI-LS/widget/widget/*.html'):
    if 'login' in f: continue
    
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
        
    # Regex to find headers object and inject Authorization
    # looking for: headers: { 'Content-Type': 'application/json' }
    # or similar
    
    new_c = re.sub(
        r"headers:\s*\{\s*['\"]Content-Type['\"]\s*:\s*['\"]application/json['\"]\s*\}",
        "headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('token') }",
        c
    )
    
    # Also handle cases where headers might be multi-line
    new_c = re.sub(
        r"headers:\s*\{\s*\n\s*['\"]Content-Type['\"]\s*:\s*['\"]application/json['\"]\s*\n\s*\}",
        "headers: {\n              'Content-Type': 'application/json',\n              'Authorization': 'Bearer ' + localStorage.getItem('token')\n            }",
        new_c
    )
    
    # Check for empty headers (GET requests)
    new_c = re.sub(
        r"fetch\((.*?)\)(.*?)\.then",
        r"fetch(\1, { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })\2.then",
        new_c
    )
    
    # Check for fetch with no options block
    # This is harder to regex safely, let's just do it manually for known files if needed.
    
    if new_c != c:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_c)
        print(f"Patched auth header in {f}")
