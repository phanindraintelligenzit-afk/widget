import sys

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'const prometheus = resources["Prometheus"] || {};' in line:
        continue
    if 'if (Object.keys(prometheus).length > 0) {' in line:
        skip = True
        continue
    if skip and '}' in line:
        skip = False
        continue
    
    if not skip:
        new_lines.append(line)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
