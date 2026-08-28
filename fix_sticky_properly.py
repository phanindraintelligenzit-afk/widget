import os

files = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

for f_path in files:
    if not os.path.exists(f_path): continue
    with open(f_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Lock the body
    if 'body {' in content:
        content = content.replace('body {\n      margin: 0;', 'body {\n      margin: 0;\n      overflow: hidden;\n      height: 100vh;')
    else:
        content = content.replace('body { margin:0;', 'body { margin:0; overflow: hidden; height: 100vh;')

    # 2. Make main-content scrollable independently
    content = content.replace(
        '.main-content {\n      flex: 1;\n      padding: 40px;\n      margin-left: 260px;\n    }',
        '.main-content {\n      flex: 1;\n      padding: 40px;\n      margin-left: 260px;\n      height: 100vh;\n      overflow-y: auto;\n      box-sizing: border-box;\n    }'
    )
    content = content.replace(
        '.main-content {\n        flex: 1;\n        padding: 40px;\n        margin-left: 260px;\n      }',
        '.main-content {\n        flex: 1;\n        padding: 40px;\n        margin-left: 260px;\n        height: 100vh;\n        overflow-y: auto;\n        box-sizing: border-box;\n      }'
    )
    
    # 3. Make header sticky exactly at the padding edge
    content = content.replace(
        'style="position: sticky; top: 0; background: var(--bg); z-index: 1000; padding-top: 20px; margin-top: -20px; display: flex;',
        'style="position: sticky; top: -40px; background: var(--bg); z-index: 1000; padding-top: 40px; margin-top: -40px; display: flex;'
    )

    with open(f_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Web app layout properly constrained!")
