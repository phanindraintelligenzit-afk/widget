import os
import re

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

HEAD = "DPI-LS (Digital Performance Index - Life Science)"

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Apply based on specific file
    if 'demo.html' in file_path:
        content = content.replace('<h1>Digital Performance Index - Life Science</h1>', f'<h1>{HEAD}</h1>')
    
    elif 'onboarding.html' in file_path:
        content = content.replace('<h1 style="margin-top: 0;">Onboard Digital Worker</h1>', 
                                  f'<h1 style="margin-top: 0; margin-bottom: 5px;">{HEAD}</h1>\n    <h2 style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Onboard Digital Worker</h2>')
        
    elif 'agent-config.html' in file_path:
        content = content.replace('<h1 style="margin-top: 0;">Configure Agent Static Data</h1>', 
                                  f'<h1 style="margin-top: 0; margin-bottom: 5px;">{HEAD}</h1>\n    <h2 style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Configure Agent Static Data</h2>')
        
    elif 'agent-profile.html' in file_path:
        content = content.replace('<h1 id="agent-name" style="margin-top: 0;">Agent Profile</h1>', 
                                  f'<h1 style="margin-top: 0; margin-bottom: 5px;">{HEAD}</h1>\n    <h2 id="agent-name" style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Agent Profile</h2>')
        
    elif 'resources.html' in file_path:
        content = content.replace('<h1>Observability Resource Evaluation</h1>', 
                                  f'<h1 style="margin-bottom: 5px;">{HEAD}</h1>\n  <h2 style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Observability Resource Evaluation</h2>')
        
    elif 'score.html' in file_path:
        content = content.replace('<h1>Agent Scores (Raw Values)</h1>', 
                                  f'<h1 style="margin-bottom: 5px;">{HEAD}</h1>\n  <h2 style="margin-top: 0; color: var(--accent); font-size: 18px; margin-bottom: 25px;">Agent Scores (Raw Values)</h2>')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        print(f"Updated heading in {file_path}")

print("Heading changes complete!")
