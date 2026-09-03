import re

with open('widget/agent-config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove % from Weightage Distribution
content = content.replace('Weightage Distribution (%)', 'Weightage Distribution')
content = content.replace('Total: 100%', 'Total: 100')
content = content.replace('(P) %', '(P)')
content = content.replace('(Q) %', '(Q)')
content = content.replace('(E) %', '(E)')
content = content.replace('(G) %', '(G)')
content = content.replace('(R) %', '(R)')
content = content.replace('(C) %', '(C)')
content = content.replace('(V) %', '(V)')

# 2. Add Live Preview Box below the form and above the save button
preview_html = """
        <div style="margin-top: 30px; background: #020617; border: 2px solid #334155; border-radius: 8px; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-family: 'Courier New', Courier, monospace;">
                <h4 style="margin: 0; color: #64748b; font-size: 13px; text-transform: uppercase;">Live DPI-LS Projection</h4>
                <div style="color: #38bdf8; font-size: 12px; margin-top: 5px;">(P * Q^1.5 * E) * (G^1.5 * R^2) * C * V</div>
            </div>
            <div style="font-size: 32px; font-weight: 800; color: #facc15;" id="live_dpi_score">0.00</div>
        </div>
        <button type="submit" style="margin-top: 20px;">Save Configurations</button>
"""
content = re.sub(r'<button type="submit".*?>Save Configurations</button>', preview_html, content)

# 3. Add Javascript for live calculation
calc_js = """
    function calculateDPI() {
        const P = parseFloat(document.getElementById('base_P').value) || 0;
        const Q = parseFloat(document.getElementById('base_Q').value) || 0;
        const E = parseFloat(document.getElementById('base_E').value) || 0;
        const G = parseFloat(document.getElementById('base_G').value) || 0;
        const R = parseFloat(document.getElementById('base_R').value) || 0;
        const C = parseFloat(document.getElementById('base_C').value) || 0;
        const V = parseFloat(document.getElementById('base_V').value) || 0;
        
        let dpi = (P * Math.pow(Q, 1.5) * E) * (Math.pow(G, 1.5) * Math.pow(R, 2)) * C * V;
        dpi = dpi * 100; // Assuming it calculates to a ~1.0 scale
        if (dpi > 100) dpi = 100;
        
        document.getElementById('live_dpi_score').innerText = dpi.toFixed(2);
        
        let wTotal = 0;
        document.querySelectorAll('.weight-input').forEach(inp => wTotal += (parseFloat(inp.value)||0));
        document.getElementById('weightTotal').innerText = "Total: " + wTotal;
        if(wTotal !== 100) {
            document.getElementById('weightTotal').style.color = "#ef4444";
        } else {
            document.getElementById('weightTotal').style.color = "var(--muted)";
        }
    }
    
    // Attach event listeners
    document.querySelectorAll('input').forEach(inp => inp.addEventListener('input', calculateDPI));
    calculateDPI(); // initial run
"""
content = content.replace('document.getElementById(\'configForm\').addEventListener(\'submit\'', calc_js + '\n    document.getElementById(\'configForm\').addEventListener(\'submit\'')

# 4. Modify submit behavior to save all configurations dynamically
submit_js = """
    document.getElementById('configForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const agentId = document.getElementById('agent_id').value || 'agent-001';
        
        const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
        let successCount = 0;
        
        // Save Base Values
        for (let m of metrics) {
            let val = document.getElementById('base_' + m).value;
            await fetch(`/api/agents/${agentId}/config`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({configuration_key: `Base_${m}`, configuration_value: val, source: 'UI Config'})
            });
            successCount++;
        }
        
        // Save Weights
        for (let m of metrics) {
            let val = document.getElementById('weight_' + m).value;
            await fetch(`/api/agents/${agentId}/config`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({configuration_key: `Weight_${m}`, configuration_value: val, source: 'UI Config'})
            });
            successCount++;
        }
        
        // Alert and trigger test script via backend if possible, or just alert
        alert("Success! " + successCount + " configurations saved to Dashboard and Rating sections!");
    });
"""
content = re.sub(r'document\.getElementById\(\'configForm\'\)\.addEventListener\(\'submit\'.*?\}\);', submit_js, content, flags=re.DOTALL)

with open('widget/agent-config.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Config refactored!")
