import os
import re

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

    # Change sidebar to fixed
    content = content.replace(
        '.sidebar {\n      width: 260px;\n      position: sticky;\n      top: 0;\n      height: 100vh;\n      overflow-y: auto;',
        '.sidebar {\n      width: 260px;\n      position: fixed;\n      top: 0;\n      left: 0;\n      height: 100vh;\n      overflow-y: auto;'
    )
    content = content.replace(
        '.sidebar {\n        width: 260px;\n        position: sticky;\n        top: 0;\n        height: 100vh;\n        overflow-y: auto;',
        '.sidebar {\n        width: 260px;\n        position: fixed;\n        top: 0;\n        left: 0;\n        height: 100vh;\n        overflow-y: auto;'
    )

    # Change main-content to have margin-left
    content = content.replace(
        '.main-content {\n      flex: 1;\n      padding: 40px;\n      overflow-y: auto;\n    }',
        '.main-content {\n      flex: 1;\n      padding: 40px;\n      margin-left: 260px;\n    }'
    )
    content = content.replace(
        '.main-content {\n        flex: 1;\n        padding: 40px;\n        overflow-y: auto;\n      }',
        '.main-content {\n        flex: 1;\n        padding: 40px;\n        margin-left: 260px;\n      }'
    )
    
    # Remove overflow-y: auto from main-content if it wasn't caught
    content = content.replace('overflow-y: auto;\n    }\n  </style>', '}\n  </style>')

    # Adjust top-header sticky to compensate for body scrolling instead of main-content scrolling
    # If body scrolls, top: 0 works beautifully for sticky elements inside main-content!
    # Because there is no padding constraint inside the body scroll
    content = content.replace(
        'style="position: sticky; top: -40px; background: var(--bg); z-index: 1000; padding-top: 40px; margin-top: -40px; display: flex;',
        'style="position: sticky; top: 0; background: var(--bg); z-index: 1000; padding-top: 20px; margin-top: -20px; display: flex;'
    )

    with open(f_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Layout fixed for fixed sidebar and natural body scrolling!")
