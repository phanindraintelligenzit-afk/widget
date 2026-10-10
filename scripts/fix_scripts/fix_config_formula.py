file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''<h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>
          <div style="font-size: 14px; color: #38bdf8; font-family: 'Courier New', monospace; margin-top: 5px;">
              DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V
          </div>'''

content = content.replace('<h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>', replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
