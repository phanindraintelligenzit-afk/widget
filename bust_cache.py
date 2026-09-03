with open('widget/demo.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('dpi-ls.js?v=3', 'dpi-ls.js?v=4')

with open('widget/demo.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Cache busted!")
