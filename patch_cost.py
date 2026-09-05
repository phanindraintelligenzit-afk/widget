import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Remove the keys from metricsMap
keys_to_remove = [
    'ai_cost_per_output',
    'human_cost_per_output',
    'utilization',
    'efficiency_ratio',
    'cost_score',
    'tco'
]

for key in keys_to_remove:
    # Match key in metricsMap
    c = re.sub(r'^\s*' + key + r':\s*\{.*?\}(,?)\n', '', c, flags=re.MULTILINE)
    # Match key in prettyNames
    c = re.sub(r'^\s*' + key + r':\s*".*?"(,?)\n', '', c, flags=re.MULTILINE)

# Remove from isDollarMetric array
c = c.replace("'ai_cost_per_output', ", "")
c = c.replace("'human_cost_per_output', ", "")
c = c.replace("'tco'", "")
# Fix any dangling commas in isDollarMetric if tco was the last one
c = c.replace(", ]", "]")
c = c.replace(",]", "]")

# Let's remove from COST_M
c = c.replace(",'AI_cost_per_output'", "")
c = c.replace(",'Human_cost_per_output'", "")
c = c.replace(",'utilization'", "")
c = c.replace(",'total_cost_of_ownership'", "")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

