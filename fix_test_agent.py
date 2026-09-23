file_path = 'examples/test_custom_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('response = monitored_agent.invoke(', 'response = my_agent.invoke(')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
