with open('api/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if '@app.get("/ratings"' in line or '@app.get("/api/ratings"' in line:
            print("Found at line:", i)
            print("".join(lines[i:i+20]))
            break
