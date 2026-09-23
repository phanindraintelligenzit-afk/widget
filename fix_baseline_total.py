file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Baseline header to include the Total span
content = content.replace(
    '''<h3 style="margin-top: 30px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">Baseline Parameter Values</h3>''',
    '''<h3 style="margin-top: 30px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">Baseline Parameter Values <span id="baselineTotal" style="float:right; color:#facc15; font-size:16px; font-weight:bold;">DPI-LS: 0.00</span></h3>'''
)

# 2. Modify the JS auto-save logic to ALSO calculate the score preview
auto_save_script = '''
      // Auto-save logic and Dynamic DPI-LS Calculation
      async function updateDynamicBaselineTotal() {
          const P = parseFloat(document.getElementById('base_P').value) || 0;
          const Q = parseFloat(document.getElementById('base_Q').value) || 0;
          const E = parseFloat(document.getElementById('base_E').value) || 0;
          const G = parseFloat(document.getElementById('base_G').value) || 0;
          const R = parseFloat(document.getElementById('base_R').value) || 0;
          const C = parseFloat(document.getElementById('base_C').value) || 0;
          const V = parseFloat(document.getElementById('base_V').value) || 0;
          
          const agentId = document.getElementById('agent_id').value || 'agent-001';
          
          try {
              const res = await fetch("/api/agents/" + agentId + "/score/preview", {
                  method: 'POST',
                  headers: {
                      'Content-Type': 'application/json',
                      'Authorization': 'Bearer ' + (localStorage.getItem('token') || '')
                  },
                  body: JSON.stringify({ P: P, Q: Q, E: E, G: G, R: R, C: C, V: V })
              });
              if(res.ok) {
                  const data = await res.json();
                  document.getElementById('baselineTotal').textContent = "DPI-LS: " + data.preview_score.toFixed(2);
              }
          } catch(e) {
              console.error(e);
          }
      }

      const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
      metrics.forEach(m => {
          const el = document.getElementById('base_' + m);
          if (el) {
              el.addEventListener('input', updateDynamicBaselineTotal);
              el.addEventListener('change', async (e) => {
                  const agentId = document.getElementById('agent_id').value || 'agent-001';
                  const val = e.target.value;
                  try {
                      await fetch("/api/agents/" + agentId + "/config", {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                          body: JSON.stringify({configuration_key: "Base_" + m, configuration_value: val, source: 'UI Config (Auto-save)'})
                      });
                  } catch (err) {}
                  updateDynamicBaselineTotal();
              });
          }
      });
      // Run once on load
      setTimeout(updateDynamicBaselineTotal, 1000);
'''

# Find my previous auto-save logic and replace it
import re
start_idx = content.find('// Auto-save logic for baseline parameters')
if start_idx != -1:
    end_idx = content.find("const configForm = document.getElementById('configForm');", start_idx)
    content = content[:start_idx] + auto_save_script + "\n      " + content[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
