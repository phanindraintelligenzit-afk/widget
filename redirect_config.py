with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We will replace the synchronous UI update inside the submit listener with a simple redirect.
new_listener = """document.getElementById('onboardingForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const agentIdVal = document.getElementById('agent_id').value;
      const descVal = document.getElementById('description').value;
      const typeVal = document.getElementById('agent_type').value;
      const envVal = document.getElementById('environment').value;
      const bizOwnerName = document.getElementById('business_owner_name').value;
      const bizEmail = document.getElementById('business_owner_email').value;
      const techOwnerName = document.getElementById('technical_owner_name').value;
      const techEmail = document.getElementById('technical_owner_email').value;
      const roleVal = document.getElementById('digital_worker_role').value;
      
      const statusEl = document.getElementById('status');
      statusEl.textContent = 'Submitting...';
      statusEl.className = 'status-msg';

      const payload = {
        description: descVal, agent_type: typeVal, environment: envVal,
        business_owner_name: bizOwnerName, business_owner_email: bizEmail,
        technical_owner_name: techOwnerName, technical_owner_email: techEmail,
        digital_worker_role: roleVal
      };
      
      try {
        await fetch(`/api/agents/${agentIdVal}/onboard`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') },
          body: JSON.stringify(payload)
        });
      } catch (e) {
        console.error("Backend sync failed:", e);
      }
      
      // Instantly redirect to the configurations page and pass the agent ID
      window.location.href = `/widget/agent-config.html?agent_id=${encodeURIComponent(agentIdVal)}`;
    });"""

pattern = re.compile(r"document\.getElementById\('onboardingForm'\)\.addEventListener\('submit', async \(e\) => \{.*?\n    \}\);", re.DOTALL)
new_content = pattern.sub(new_listener, content)

# Also remove the two-column grid layout so the form is centered normally again
grid_start = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: start;">\n      <form id="onboardingForm">'
new_content = new_content.replace(grid_start, '<form id="onboardingForm">')

grid_end = """</form>
      
      <div id="onboarding-preview" style="background:#020617; border-radius:10px; border:2px solid #334155; padding: 24px; font-family:'Courier New',Courier,monospace; display: none; height: 100%; box-sizing: border-box;">
         <h3 style="color:#facc15; margin-top:0; font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; letter-spacing: 1px;">AGENT ONBOARDED</h3>
         <div id="preview-content" style="color: #e2e8f0; font-size: 13px; line-height: 1.8;"></div>
      </div>
      </div>"""
new_content = new_content.replace(grid_end, '</form>')

# Restore page max-width
new_content = new_content.replace('.page-body { max-width: 1200px; width: 100%; }', '.page-body { max-width: 800px; }')

if new_content == content:
    print("Failed to replace!")
else:
    with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Redirect applied!")
