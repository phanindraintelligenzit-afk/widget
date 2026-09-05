with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_func = False
for i, line in enumerate(lines):
    if 'function renderCostTableHtml' in line:
        in_func = True
        print(f"Line {i}: {line.strip()}")
    if in_func and 'function calculateValidationMetrics' in line:
        break
    if in_func:
        print(line.rstrip('\n').encode('ascii', 'ignore').decode('ascii'))
