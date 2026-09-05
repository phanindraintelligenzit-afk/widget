import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('&#36;{aiCostVal}', '${aiCostVal}')
c = c.replace('&#36;{utilVal}', '${utilVal}')
c = c.replace('&#36;{resourceFilter', '${resourceFilter')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
