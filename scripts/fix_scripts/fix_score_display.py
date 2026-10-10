file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove from static HTML
content = content.replace(
    '''DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V = 0.00''',
    '''DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V'''
)

# 2. Update JavaScript to remove the score appendage
old_js = '''document.getElementById('baselineTotal').innerHTML = "DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V = " + data.preview_score.toFixed(2);'''
new_js = '''document.getElementById('baselineTotal').innerHTML = "DPI-LS = (P &times; Q^1.5 &times; E) &times; (G^1.5 &times; R^2) &times; C &times; V";'''
content = content.replace(old_js, new_js)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
