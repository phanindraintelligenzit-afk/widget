with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()
start = 0
for i, line in enumerate(lines):
    if 'function renderQualityTableHtml' in line:
        start = i
        break
for i in range(start, start+75):
    if i < len(lines):
        print(lines[i].strip().encode('ascii', 'ignore').decode('ascii'))
