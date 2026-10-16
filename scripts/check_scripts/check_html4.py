with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'Cost (5%)' in line:
        for j in range(i-5, i+20):
            if j < len(lines):
                print(lines[j].strip().encode('ascii', 'ignore').decode('ascii'))
        break
