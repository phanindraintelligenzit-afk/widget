with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_func = False
start = 0
for i, line in enumerate(lines):
    if 'function renderCostTableHtml' in line:
        in_func = True
    if in_func and 'const METRIC_NICE_NAMES' in line:
        start = i
        break

if start > 0:
    for j in range(start, start+25):
        if j < len(lines):
            print(lines[j].strip().encode('ascii', 'ignore').decode('ascii'))
