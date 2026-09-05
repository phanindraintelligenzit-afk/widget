with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_func = False
for i, line in enumerate(lines):
    if 'function renderCostTableHtml' in line:
        in_func = True
        print(f"Line {i}: {line.strip()}")
    if in_func and 'COST TRACEABILITY & EFFICIENCY' in line:
        for j in range(i-5, i+25):
            if j < len(lines):
                print(lines[j].strip())
        break
