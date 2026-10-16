file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Update updateDynamicBaselineTotal in UI to use '+'
old_js = '''              // Update formula string
              const formulaStr = "DPI-LS = (" + formulaParts[0] + " &times; " + formulaParts[1] + " &times; " + formulaParts[2] + ") &times; (" + formulaParts[3] + " &times; " + formulaParts[4] + ") &times; " + formulaParts[5] + " &times; " + formulaParts[6];
              document.getElementById('baselineTotal').innerHTML = formulaStr;'''

new_js = '''              // Update formula string
              const formulaStr = "DPI-LS = " + formulaParts.join(" + ");
              document.getElementById('baselineTotal').innerHTML = formulaStr;'''

content = content.replace(old_js, new_js)

# Also update the static string
old_static = 'DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V'
new_static = 'DPI-LS = P + Q^1.5 + E + G^1.5 + R^2 + C + V'
content = content.replace(old_static, new_static)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
