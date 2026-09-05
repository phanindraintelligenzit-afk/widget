with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if i == 819 and line.strip() == '}':
        continue
    new_lines.append(line)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
