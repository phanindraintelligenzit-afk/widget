file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''<h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>
          <div style="font-size: 14px; color: #38bdf8; font-family: 'Courier New', monospace; margin-top: 5px;">
              DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V
          </div>'''

new_block = '''<div style="display: flex; flex-direction: column;">
              <h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>
              <div style="font-size: 13px; color: #38bdf8; font-family: 'Courier New', monospace; margin-top: 5px;">
                  DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V
              </div>
          </div>'''

content = content.replace(old_block, new_block)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
