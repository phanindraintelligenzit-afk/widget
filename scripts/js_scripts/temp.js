
    // Pre-fill Agent ID from URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const passedAgentId = urlParams.get('agent_id');
    if (passedAgentId) {
        document.getElementById('agent_id').value = passedAgentId;
    }
    
    async function calculateDPI() {
        const P = parseFloat(1.0) || 0;
        const Q = parseFloat(1.0) || 0;
        const E = parseFloat(1.0) || 0;
        const G = parseFloat(1.0) || 0;
        const R = parseFloat(1.0) || 0;
        const C = parseFloat(1.0) || 0;
        const V = parseFloat(1.0) || 0;
        const wP = parseFloat(document.getElementById('weight_P').value) || 0;
        const wQ = parseFloat(document.getElementById('weight_Q').value) || 0;
        const wE = parseFloat(document.getElementById('weight_E').value) || 0;
        const wG = parseFloat(document.getElementById('weight_G').value) || 0;
        const wR = parseFloat(document.getElementById('weight_R').value) || 0;
        const wC = parseFloat(document.getElementById('weight_C').value) || 0;
        const wV = parseFloat(document.getElementById('weight_V').value) || 0;
        
        
        let wTotal = 0;
        document.querySelectorAll('.weight-input').forEach(inp => {
            wTotal += (parseFloat(inp.value)||0);
        });
        const wTotalEl = document.getElementById('weightTotal');
        if (wTotalEl) {
            wTotalEl.innerText = "Total: " + wTotal;
            if(wTotal !== 100) {
                wTotalEl.style.color = "#ef4444";
            } else {
                wTotalEl.style.color = "var(--muted)";
            }
        }
    }
    
    document.querySelectorAll('input').forEach(inp => inp.addEventListener('input', calculateDPI));
    calculateDPI();

    
      
      

      const configForm = document.getElementById('configForm');
    if(configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const agentId = document.getElementById('agent_id').value || 'agent-001';
            const metrics = ['P', 'Q', 'E', 'G', 'R', 'C', 'V'];
            
            
              // --- Weight Validation Blocker ---
            let checkTotal = 0;
            for (let m of metrics) {
                checkTotal += (parseFloat(document.getElementById('weight_' + m).value) || 0);
            }
            if (checkTotal !== 100) {
                alert(`WARNING: The total Weightage Distribution must equal exactly 100.\n\nYour current total is: ${checkTotal}\n\nPlease adjust the weights before saving.`);
                return;
            }
            // ---------------------------------
            
                          const statusEl = document.getElementById('status');
              if (statusEl) {
                  statusEl.textContent = 'Saving Configurations...';
                  statusEl.className = 'status-msg';
              }
              
              const payload = {
                  weight_p: parseFloat(document.getElementById('weight_P').value) || 0,
                  weight_q: parseFloat(document.getElementById('weight_Q').value) || 0,
                  weight_e: parseFloat(document.getElementById('weight_E').value) || 0,
                  weight_g: parseFloat(document.getElementById('weight_G').value) || 0,
                  weight_r: parseFloat(document.getElementById('weight_R').value) || 0,
                  weight_v: parseFloat(document.getElementById('weight_V').value) || 0,
                  weight_c: parseFloat(document.getElementById('weight_C').value) || 0
              };

              try {
                  const res = await fetch(`/api/agents/${agentId}/weightages`, {
                      method: 'PUT',
                      headers: {
                          'Content-Type': 'application/json',
                          'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')
                      },
                      body: JSON.stringify(payload)
                  });
                  
                  if (!res.ok) {
                      throw new Error("Failed to save. Check that totals equal exactly 100.");
                  }
                  
                                    if (statusEl) {
                      statusEl.textContent = 'Configurations saved! Generating Telemetry...';
                      statusEl.className = 'status-msg success';
                  }
                  
                  await fetch(`/api/agents/${agentId}/run_telemetry`, {
                      method: 'POST',
                      headers: {'Authorization': 'Bearer ' + (localStorage.getItem('token')||'')}
                  });
                  
                  if (statusEl) {
                      statusEl.textContent = 'Success! Redirecting to Dashboard...';
                  }
                  
                  setTimeout(() => {
                      window.location.href = '/widget/demo.html';
                  }, 1500);
                  
              } catch (err) {
                  if (statusEl) {
                      statusEl.textContent = err.message;
                      statusEl.className = 'status-msg error'; } } }); }

