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

    # The current style starts with `style="display: flex; justify-content: flex-end;`
    old_style = 'class="top-header" style="display: flex;'
    new_style = 'class="top-header" style="position: sticky; top: -40px; background: var(--bg); z-index: 1000; padding-top: 40px; margin-top: -40px; display: flex;'
    
    content = content.replace(old_style, new_style)

    with open(f_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Top header made sticky!")
