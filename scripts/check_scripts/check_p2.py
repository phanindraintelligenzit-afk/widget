with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()
start = 0
for i, line in enumerate(lines):
    if '<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Human Baseline</div>' in line:
        start = i
        break
for i in range(start, start+35):
    if i < len(lines):
        print(lines[i].strip().encode('ascii', 'ignore').decode('ascii'))
