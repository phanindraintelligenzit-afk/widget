import sys

def check_braces(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        c = f.read()
    
    lines = c.split('\n')
    brace_count = 0
    for i, line in enumerate(lines):
        for char in line:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
        if brace_count < 0:
            print(f"Negative brace count at line {i+1}: {line}")
            return
            
    print(f"Final brace count: {brace_count}")

check_braces('widget/dpi-ls.js')
