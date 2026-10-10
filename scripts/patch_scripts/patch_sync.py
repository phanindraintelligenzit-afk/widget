import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    'metrics["G"] = float(g_sub["Formula Output"])',
    'print(f"SYNCING G: {metrics.get(\'G\')} -> {g_sub[\'Formula Output\']}"); metrics["G"] = float(g_sub["Formula Output"])'
)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)
