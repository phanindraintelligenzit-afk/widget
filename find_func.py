import os
for root, dirs, files in os.walk('.'):
    if '.venv' in root or '.git' in root: continue
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                content = f.read()
                if 'def get_session_factory' in content:
                    print(os.path.join(root, file))
