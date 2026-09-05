with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_func = False
start_i = 0
for i, line in enumerate(lines):
    if 'function renderCostTableHtml' in line:
        in_func = True
    if in_func and 'COST TRACEABILITY & EFFICIENCY' in line:
        start_i = i - 5
        break

if start_i > 0:
    for j in range(start_i, start_i+40):
        if j < len(lines):
            print(lines[j].strip().encode('ascii', 'ignore').decode('ascii'))
