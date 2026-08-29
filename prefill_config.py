with open('widget/agent-config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add javascript to parse URL parameters and fill the Agent ID input on load
js_code = """
    // Pre-fill Agent ID from URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const passedAgentId = urlParams.get('agent_id');
    if (passedAgentId) {
        document.getElementById('agent_id').value = passedAgentId;
    }
    
    function calculateDPI() {"""

content = content.replace("function calculateDPI() {", js_code)

with open('widget/agent-config.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Prefill logic injected!")
