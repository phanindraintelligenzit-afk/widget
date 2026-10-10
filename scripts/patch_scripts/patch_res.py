import re
with open('widget/resources.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix syntax error
c = re.sub(r'^\s*:\s*\{\s*url:\s*\'http://localhost:3200\',\s*online:\s*false\s*\},.*$', '', c, flags=re.MULTILINE)

# Fix riskResources array
c = re.sub(r'const riskResources = \[.*?\];', 'const riskResources = ["Falco", "Sentry", "Prometheus"];', c)

with open('widget/resources.html', 'w', encoding='utf-8') as f:
    f.write(c)
