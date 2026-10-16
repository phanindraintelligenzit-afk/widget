import re

def patch_onboarding():
    with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the try/catch block for fetch and replace it
    pattern = re.compile(r'try\s*\{\s*await fetch\(`\/api\/agents\/\$\{agentIdVal\}\/onboard`.*?catch\s*\([^)]*\)\s*\{[^}]*\}\s*', re.DOTALL)
    
    replacement = """// Fire the fetch asynchronously and DO NOT wait for it to finish
        fetch(`/api/agents/${agentIdVal}/onboard`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') },
          body: JSON.stringify(payload)
        }).catch(e => console.error("Backend sync failed:", e));
        \n        """
        
    if not pattern.search(content):
        print("Failed to find pattern in onboarding.html")
        return
        
    content = pattern.sub(replacement, content)

    with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully patched onboarding.html with regex")

if __name__ == '__main__':
    patch_onboarding()
