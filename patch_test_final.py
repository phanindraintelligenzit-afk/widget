import re
with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('os.environ["OPENAI_API_KEY"] = "sk-dummy"\n', '')
c = c.replace('logging.getLogger("litellm").setLevel(logging.CRITICAL)\n', 'logging.getLogger("litellm").setLevel(logging.CRITICAL)\nlogging.getLogger("agents").setLevel(logging.CRITICAL)\n')

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(c)
