with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'if not os.getenv("AGENTOPS_API_KEY"):',
    'if not os.getenv("AGENTOPS_API_KEY") or "rotated" in os.getenv("AGENTOPS_API_KEY", "").lower() or "{" in os.getenv("AGENTOPS_API_KEY", ""):'
)

with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(content)
