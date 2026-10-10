import sys

def patch_onboarding():
    with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
        content = f.read()

    target = """        try {
          await fetch(`/api/agents/${agentIdVal}/onboard`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') },
            body: JSON.stringify(payload)
          });
        } catch (e) {
          console.error("Backend sync failed:", e);
        }
        
        // Instantly redirect to the configurations page and pass the agent ID
        window.location.href = `/widget/agent-config.html?agent_id=${encodeURIComponent(agentIdVal)}`;"""
        
    replacement = """        // Fire the fetch asynchronously and DO NOT wait for it to finish
        fetch(`/api/agents/${agentIdVal}/onboard`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') },
          body: JSON.stringify(payload)
        }).catch(e => console.error("Backend sync failed:", e));
        
        // Instantly redirect to the configurations page and pass the agent ID
        window.location.href = `/widget/agent-config.html?agent_id=${encodeURIComponent(agentIdVal)}`;"""

    if target not in content:
        print("Failed to find target in onboarding.html")
        sys.exit(1)

    content = content.replace(target, replacement)

    with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully patched onboarding.html to redirect instantly")

if __name__ == '__main__':
    patch_onboarding()
