with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

js_content = js_content.replace('AGENT DEPARTURES', 'AGENT SCORING DASHBOARD')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

# Bust cache in demo.html
with open('widget/demo.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# increment v=4 to v=5
html_content = html_content.replace('dpi-ls.js?v=4', 'dpi-ls.js?v=5')
html_content = html_content.replace('dpi-ls.js?v=3', 'dpi-ls.js?v=5')

with open('widget/demo.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Changed AGENT DEPARTURES to AGENT SCORING DASHBOARD")
