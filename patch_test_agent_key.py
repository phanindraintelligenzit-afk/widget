with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('import os\n', 'import os\nos.environ["OPENAI_API_KEY"] = "sk-dummy"\n')

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
