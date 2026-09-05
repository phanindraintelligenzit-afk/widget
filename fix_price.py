import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'Input Tokens.*?Price', 'Input Tokens * Dollar', c)
c = re.sub(r'Output Tokens.*?Price', 'Output Tokens * Dollar', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
