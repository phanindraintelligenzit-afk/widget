import os

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

BAD_LOGO_DIV = """<div style="padding: 0 32px; display: flex; align-items: center; justify-content: center;">
        <!-- Using placeholder or icon for logo if needed -->
      </div>"""

GOOD_LOGO_DIV = """<div style="padding: 0 32px; display: flex; align-items: center; justify-content: center;">
        <img src="intelligenz-logo.png" alt="Intelligenz IT Logo" style="max-width: 180px;">
      </div>"""

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if BAD_LOGO_DIV in content:
        content = content.replace(BAD_LOGO_DIV, GOOD_LOGO_DIV)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Fixed logo in {file_path}")

print("Logo check complete!")
