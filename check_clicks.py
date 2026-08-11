import re
with open('d:/DPI-LS/widget/widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    js = f.read()

lines = js.split('\n')
for i, line in enumerate(lines):
    if 'addEvent' in line or 'onClick' in line or 'onclick' in line or 'click' in line.lower():
        print(f'{i}: {line.strip()}')
