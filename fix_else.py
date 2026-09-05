lines = open('api/scoring.py', 'r', encoding='utf-8').readlines()
for i, l in enumerate(lines):
    if l.strip() == 'else:' and 'g_formula_output' in lines[i+1]:
        lines[i] = '        pass\n'

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
