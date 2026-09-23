file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
old_js = '''              await fetch("/api/agents/" + agentId + "/config", {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                  body: JSON.stringify({configuration_key: key, configuration_value: val, source: 'UI Config (Auto-save)'})
              });'''

new_js = '''              const res = await fetch("/api/agents/" + agentId + "/config", {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                  body: JSON.stringify({configuration_key: key, configuration_value: val, source: 'UI Config (Auto-save)'})
              });
              if (res.status === 401) {
                  window.location.href = '/widget/admin-login.html';
              }'''

content = content.replace(old_js, new_js)

old_preview = '''              const res = await fetch("/api/agents/" + agentId + "/score/preview", {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify(payload)
              });
              const data = await res.json();'''
              
new_preview = '''              const res = await fetch("/api/agents/" + agentId + "/score/preview", {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                  body: JSON.stringify(payload)
              });
              if (res.status === 401) {
                  window.location.href = '/widget/admin-login.html';
                  return;
              }
              const data = await res.json();'''

content = content.replace(old_preview, new_preview)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
