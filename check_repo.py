with open('api/repo.py', 'r', encoding='utf-8') as f:
    content = f.read()
    import re
    match = re.search(r'def latest_scores_for_all.*?return\s+\[.*?\]', content, re.DOTALL)
    if match:
        print(match.group(0))
    else:
        # Just grab the function definition
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if 'def latest_scores_for_all' in line:
                print("\\n".join(lines[i:i+20]))
                break
