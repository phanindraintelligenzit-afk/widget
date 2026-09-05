with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'function renderCostTableHtml' in line:
        for j in range(i, i+150):
            if j < len(lines):
                if 'function calculateValidationMetrics' in lines[j]:
                    break
                print(lines[j].strip().encode('ascii', 'ignore').decode('ascii'))
        break
