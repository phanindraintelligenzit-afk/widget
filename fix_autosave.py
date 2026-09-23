file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

auto_save_script = '''
      // Auto-save logic for baseline parameters
      const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
      metrics.forEach(m => {
          const el = document.getElementById('base_' + m);
          if (el) {
              el.addEventListener('change', async (e) => {
                  const agentId = document.getElementById('agent_id').value || 'agent-001';
                  const val = e.target.value;
                  try {
                      await fetch(/api/agents/ + agentId + /config, {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                          body: JSON.stringify({configuration_key: Base_ + m, configuration_value: val, source: 'UI Config (Auto-save)'})
                      });
                      console.log(Auto-saved Base_ + m +  =  + val);
                  } catch (err) {
                      console.error('Failed to auto-save', err);
                  }
              });
          }
      });
'''

# Find the end of the script tag and inject the auto-save script
content = content.replace('''// --- Weight Validation Blocker ---''', auto_save_script + '''\n              // --- Weight Validation Blocker ---''')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
