with open('api/scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'r_max = settings.r_max if hasattr(settings, "r_max") else 50.0',
    'r_max = 50.0'
)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
