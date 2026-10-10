file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('RAW-Score', 'Baseline Parameter Values')
content = content.replace('Total: 100</span>', 'Total: 100%</span>')
content = content.replace('<h3>Weightage Distribution', '<h3>Weightage Distribution (%)')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
