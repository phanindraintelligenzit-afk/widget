with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'metricsMap["Prometheus' in line:
        continue
    if 'if (Object.keys(prometheus).length > 0) {' in line:
        continue
    if 'const prometheus =' in line:
        continue
    
    # Wait, my previous script left an orphaned `}` at line 37!
    # Let me just clear that specific line out.
    new_lines.append(line)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
