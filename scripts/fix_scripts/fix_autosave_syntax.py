file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('/api/agents/ + agentId + /config', '\"/api/agents/\" + agentId + \"/config\"')
content = content.replace('Base_ + m', '\"Base_\" + m')
content = content.replace('Auto-saved Base_ + m +  =  + val', '\"Auto-saved Base_\" + m + \" = \" + val')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
