file_path = 'widget/agent-profile.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('''alert('Failed to retire agent.');''', '''if(res.status === 401) { alert('Session expired. Please log in again.'); window.location.href='/widget/admin-login.html'; } else { alert('Failed to retire agent.'); }''')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
