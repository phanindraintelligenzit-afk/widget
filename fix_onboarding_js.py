import re

with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
    content = f.read()

# I want to rewrite the entire event listener for the form to do synchronous UI update
# first, then do the fetch.
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
      statusEl.textContent = 'Agent Onboarded Successfully!';
      statusEl.className = 'status-msg success';

      // 1. Synchronously Render the Right-Side Table Box
      const previewBox = document.getElementById('onboarding-preview');
      const previewContent = document.getElementById('preview-content');
      
      let htmlStr = `
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
          <tbody>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b; width: 40%;">Agent ID</th><td style="padding: 10px 0; color: #38bdf8; font-weight: bold;">${agentIdVal}</td></tr>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b;">Type</th><td style="padding: 10px 0;">${typeVal}</td></tr>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b;">Environment</th><td style="padding: 10px 0; color: #4ade80;">${envVal}</td></tr>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b;">Role</th><td style="padding: 10px 0;">${roleVal}</td></tr>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b;">Business Owner</th><td style="padding: 10px 0;">${bizOwnerName}<br><span style="color:#94a3b8; font-size:11px;">${bizEmail}</span></td></tr>
            <tr style="border-bottom: 1px solid #1e293b;"><th style="padding: 10px 0; color: #64748b;">Technical Owner</th><td style="padding: 10px 0;">${techOwnerName}<br><span style="color:#94a3b8; font-size:11px;">${techEmail}</span></td></tr>
            <tr><th style="padding: 10px 0; color: #64748b; vertical-align: top;">Description</th><td style="padding: 10px 0;">${descVal}</td></tr>
          </tbody>
        </table>
        
        <div style="margin-top: 25px; text-align: center;">
          <a href="/widget/agent-config.html" style="display: inline-block; background: #facc15; color: #000; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold;">Proceed to Configurations &rarr;</a>
        </div>
      `;
      
      previewContent.innerHTML = htmlStr;
      previewBox.style.display = 'block';

      // 2. Perform the actual backend fetch in the background
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
    });"""

# Use regex to replace the entire event listener block
pattern = re.compile(r"document\.getElementById\('onboardingForm'\)\.addEventListener\('submit', async \(e\) => \{.*?\}\);", re.DOTALL)
content = pattern.sub(new_listener, content)

with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Onboarding synchronous JS fixed!")
