import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'^\s*const presidio = resources\["Microsoft Presidio"\].*?$\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*if \(Object\.keys\(presidio\)\.length > 0\) \{[\s\S]*?^\s*\}\n', '', c, flags=re.MULTILINE)
c = c.replace('"Microsoft Presidio", ', '')
c = c.replace('"Microsoft Presidio"', '')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

