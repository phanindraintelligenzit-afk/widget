import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace humanCostPerOutput hardcode
content = content.replace("const humanCostPerOutput = 200.0;", "const humanCostPerOutput = getNum(settings, 'baseline_human_output', 200.0);")

# For the calculation matching logic, we can leave it as is if it's meant to verify the backend calculations, but the prompt says "Remove them if they exist and wire them to the backend."
# I'll replace the hardcoded "val: 200.0, calc: 200.0, disp: 200.0" with humanCostPerOutput
content = content.replace("human_cost: { val: 200.0, calc: 200.0, disp: 200.0, formula: \"Hardcoded Baseline\", src: \"DPI-LS Settings\", resource: \"Baseline\", dec: 2 }", "human_cost: { val: humanCostPerOutput, calc: humanCostPerOutput, disp: humanCostPerOutput, formula: \"Baseline\", src: \"DPI-LS Settings\", resource: \"Baseline\", dec: 2 }")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched dpi-ls.js")
