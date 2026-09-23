file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Update updateDynamicBaselineTotal
old_js = '''      // Auto-save logic and Dynamic DPI-LS Calculation
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
                  document.getElementById('baselineTotal').innerHTML = "DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V";
              }
          } catch(e) {
              console.error(e);
          }
      }'''

new_js = '''      // Auto-save logic and Dynamic DPI-LS Calculation
      async function updateDynamicBaselineTotal() {
          const payload = {};
          const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
          let formulaParts = [];
          
          metrics.forEach(m => {
              payload[m] = parseFloat(document.getElementById('base_' + m).value) || 0;
              payload['Mult_' + m] = parseFloat(document.getElementById('mult_' + m).value) || 1.0;
              payload['Pow_' + m] = parseFloat(document.getElementById('pow_' + m).value) || 1.0;
              
              let part = m;
              if (payload['Mult_' + m] !== 1.0) part = payload['Mult_' + m] + "*" + part;
              if (payload['Pow_' + m] !== 1.0) part = part + "^" + payload['Pow_' + m];
              formulaParts.push(part);
          });
          
          const agentId = document.getElementById('agent_id').value || 'agent-001';
          
          try {
              const res = await fetch("/api/agents/" + agentId + "/score/preview", {
                  method: 'POST',
                  headers: {
                      'Content-Type': 'application/json',
                      'Authorization': 'Bearer ' + (localStorage.getItem('token') || '')
                  },
                  body: JSON.stringify(payload)
              });
              
              // Update formula string
              const formulaStr = "DPI-LS = (" + formulaParts[0] + " &times; " + formulaParts[1] + " &times; " + formulaParts[2] + ") &times; (" + formulaParts[3] + " &times; " + formulaParts[4] + ") &times; " + formulaParts[5] + " &times; " + formulaParts[6];
              document.getElementById('baselineTotal').innerHTML = formulaStr;
              
          } catch(e) {
              console.error(e);
          }
      }'''

content = content.replace(old_js, new_js)

# Update auto-save loop to attach listeners to mult_ and pow_ as well
old_loop = '''      const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
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
      });'''

new_loop = '''      const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
      
      async function autoSave(key, val) {
          const agentId = document.getElementById('agent_id').value || 'agent-001';
          try {
              await fetch("/api/agents/" + agentId + "/config", {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')},
                  body: JSON.stringify({configuration_key: key, configuration_value: val, source: 'UI Config (Auto-save)'})
              });
          } catch (err) {}
      }

      metrics.forEach(m => {
          const types = [
            {prefix: 'base_', key: 'Base_'}, 
            {prefix: 'mult_', key: 'Multiplier_'}, 
            {prefix: 'pow_', key: 'Power_'}
          ];
          
          types.forEach(t => {
              const el = document.getElementById(t.prefix + m);
              if (el) {
                  el.addEventListener('input', updateDynamicBaselineTotal);
                  el.addEventListener('change', async (e) => {
                      await autoSave(t.key + m, e.target.value);
                      updateDynamicBaselineTotal();
                  });
              }
          });
          
          // Also attach auto-save to weights
          const w_el = document.getElementById('weight_' + m);
          if (w_el) {
              w_el.addEventListener('change', async (e) => {
                  await autoSave('Weight_' + m, e.target.value);
              });
          }
      });'''

content = content.replace(old_loop, new_loop)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
