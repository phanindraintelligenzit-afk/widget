with open('examples/test_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'logging.getLogger("litellm").setLevel(logging.CRITICAL)',
    'logging.getLogger("litellm").setLevel(logging.CRITICAL)\nlogging.getLogger("dpi_ls.evaluator").setLevel(logging.CRITICAL)'
)

with open('examples/test_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
