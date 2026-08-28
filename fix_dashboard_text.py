import re

# 1. Update dpi-ls.js
with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

js_content = js_content.replace('AGENT DEPARTURES', 'AGENT SCORING DASHBOARD')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

# 2. Update demo.html
with open('widget/demo.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

pattern = re.compile(r'<p class="sub" style="font-size:15px; font-weight:500; margin-top:8px;">.*?</p>', re.DOTALL)
html_content = pattern.sub('', html_content)
html_content = html_content.replace('<h2 id="latest-card-title">Per-agent card</h2>', '<h2 id="latest-card-title">Live Agent Telemetry Feed</h2>')

with open('widget/demo.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Dashboard text updated successfully!")
