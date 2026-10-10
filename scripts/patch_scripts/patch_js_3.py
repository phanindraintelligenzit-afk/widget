import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    'const eScoreVal = calcEScore;\n\n    return {',
    'const eScoreVal = calcEScore;\n\n    return {\n      eScoreVal: eScoreVal,'
)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
