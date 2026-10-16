import re
with open('api/scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Hardcode r_max = 50.0
content = content.replace(
    'r_max = settings.r_max if hasattr(settings, "r_max") else 50.0',
    'r_max = 50.0'
)

# Remove unused dict initializations
content = re.sub(r'    llmguard = \{.*?\}\n', '', content)
content = re.sub(r'    rebuff = \{.*?\}\n', '', content)
content = re.sub(r'    trulens = \{.*?\}\n', '', content)
content = re.sub(r'    prometheus = \{.*?\}\n', '', content)

# Remove unused elif blocks
content = re.sub(r'        elif src == "LLMGuard":\n(?:            .*?\n)*', '', content)
content = re.sub(r'        elif src == "Rebuff":\n(?:            .*?\n)*', '', content)
content = re.sub(r'        elif src == "TruLens":\n(?:            .*?\n)*', '', content)
content = re.sub(r'        elif src == "Prometheus":\n(?:            .*?\n)*', '', content)

# Remove unused keys in sub_metrics["R"].update
content = re.sub(r'            "LLMGuard": llmguard,\n', '', content)
content = re.sub(r'            "Rebuff": rebuff,\n', '', content)
content = re.sub(r'            "TruLens": trulens,\n', '', content)
content = re.sub(r'            "Prometheus": prometheus\n', '', content)
content = content.replace('"Sentry": sentry,', '"Sentry": sentry')

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
