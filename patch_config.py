# -*- coding: utf-8 -*-
from pathlib import Path
html = Path('widget/agent-config.html').read_text(encoding='utf-8')
idx_start = html.find('function calculateDPI()')
idx_end = html.find('document.querySelectorAll(', idx_start)
if idx_start != -1 and idx_end != -1:
    new_calc = '''async function calculateDPI() {
        const P = parseFloat(document.getElementById('base_P').value) || 0;
        const Q = parseFloat(document.getElementById('base_Q').value) || 0;
        const E = parseFloat(document.getElementById('base_E').value) || 0;
        const G = parseFloat(document.getElementById('base_G').value) || 0;
        const R = parseFloat(document.getElementById('base_R').value) || 0;
        const C = parseFloat(document.getElementById('base_C').value) || 0;
        const V = parseFloat(document.getElementById('base_V').value) || 0;
        const wP = parseFloat(document.getElementById('weight_P').value) || 0;
        const wQ = parseFloat(document.getElementById('weight_Q').value) || 0;
        const wE = parseFloat(document.getElementById('weight_E').value) || 0;
        const wG = parseFloat(document.getElementById('weight_G').value) || 0;
        const wR = parseFloat(document.getElementById('weight_R').value) || 0;
        const wC = parseFloat(document.getElementById('weight_C').value) || 0;
        const wV = parseFloat(document.getElementById('weight_V').value) || 0;
        const agentId = new URLSearchParams(window.location.search).get('agent_id') || 'agent-001';
        try {
            const res = await fetch(/api/agents/+agentId+/score/preview, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ P, Q, E, G, R, V, C, wP, wQ, wE, wG, wR, wV, wC })
            });
            if(res.ok) {
                const data = await res.json();
                document.getElementById('dpi-projection').textContent = data.preview_score.toFixed(1);
            }
        } catch(e) {
            console.error(e);
        }
    }
    '''
    html = html[:idx_start] + new_calc + html[idx_end:]
    Path('widget/agent-config.html').write_text(html, encoding='utf-8')
    print("Replaced")
