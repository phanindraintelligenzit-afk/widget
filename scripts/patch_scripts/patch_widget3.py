import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('resources[]', 'resources["Unknown"]')
c = c.replace('res[]', 'res["Unknown"]')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

