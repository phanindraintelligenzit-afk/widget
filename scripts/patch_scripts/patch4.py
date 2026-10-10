with open('api/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'with SessionLocal() as session:' in line:
        if i + 1 < len(lines) and 'except Exception' in lines[i+1]:
            lines.insert(i + 1, '                        pass\n')
            break

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
