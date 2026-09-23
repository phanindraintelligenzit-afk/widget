with open('api/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'BoardRow(' in line:
            print("".join(lines[i:i+25]))
