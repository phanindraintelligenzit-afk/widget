file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove formula from the top header
old_header = '''<div style="display: flex; flex-direction: column;">
              <h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>
              <div style="font-size: 13px; color: #38bdf8; font-family: 'Courier New', monospace; margin-top: 5px;">
                  DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V
              </div>
          </div>'''
new_header = '''<h1 style="margin: 0; font-size: 22px;">DPI-LS (Digital Performance Index - Life Science)</h1>'''
content = content.replace(old_header, new_header)

# 2. Update the initial span text
content = content.replace(
    '''<span id="baselineTotal" style="float:right; color:#facc15; font-size:16px; font-weight:bold;">DPI-LS: 0.00</span>''',
    '''<span id="baselineTotal" style="float:right; color:#facc15; font-size:14px; font-weight:bold;">DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V = 0.00</span>'''
)

# 3. Update the JavaScript
old_js = '''document.getElementById('baselineTotal').textContent = "DPI-LS: " + data.preview_score.toFixed(2);'''
new_js = '''document.getElementById('baselineTotal').innerHTML = "DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V = " + data.preview_score.toFixed(2);'''
content = content.replace(old_js, new_js)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
