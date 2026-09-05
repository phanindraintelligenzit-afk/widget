with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_func = False
start = 0
for i, line in enumerate(lines):
    if 'function calculateValidationMetrics' in line:
        in_func = True
        start = i
        break

if start > 0:
    for j in range(start, start+60):
        if j < len(lines):
            print(lines[j].strip().encode('ascii', 'ignore').decode('ascii'))
