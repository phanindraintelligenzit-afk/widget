with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

import re
matches = re.findall(r'function renderCostTableHtml.*?return (.*?);', c, re.DOTALL)
if matches:
    print(matches[0][:1500])
