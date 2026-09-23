import re

file_path = 'widget/agent-profile.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add a check for 401 to redirect to login
content = content.replace('''if(data.detail) return;''', '''if(data.detail) { if (r.status === 401) window.location.href='/widget/admin-login.html'; return; }''')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
