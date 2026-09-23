file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('console.log(Auto-saved "Base_" + m +  =  + val);', 'console.log("Auto-saved Base_" + m + " = " + val);')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
