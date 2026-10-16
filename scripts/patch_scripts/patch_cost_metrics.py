import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace "Price" with "$" in formulas
c = c.replace('formula: "Input Tokens * Price"', 'formula: "Input Tokens * $"')
c = c.replace('formula: "Output Tokens * Price"', 'formula: "Output Tokens * $"')

# Replace the A- string issue if it exists
c = c.replace('Input Tokens A- Price', 'Input Tokens * $')
c = c.replace('Output Tokens A- Price', 'Output Tokens * $')

# Hardcode  human cost row
c = c.replace("const humanCostPerOutput = getNum(sub, 'Human Cost / Output', getNum(settings, 'human_cost_per_output'));", "const humanCostPerOutput = 200.0;")

c = c.replace('model_cost: { val: modelCost, calc: calcModelCost, disp: modelCost, formula: "Prompt Cost + Completion Cost", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 6 },', '''model_cost: { val: modelCost, calc: calcModelCost, disp: modelCost, formula: "Prompt Cost + Completion Cost", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 6 },
        human_cost: { val: 200.0, calc: 200.0, disp: 200.0, formula: "Hardcoded Baseline", src: "DPI-LS Settings", resource: "Baseline", dec: 2 },
        ai_cost_per_output: { val: aiCostPerOutput, calc: calcAiCostPerOutput, disp: aiCostPerOutput, formula: "Total Model Cost / Completed Outputs", src: "DPI-LS Engine", resource: "Calculation", dec: 6 },
        efficiency_ratio: { val: efficiencyRatio, calc: calcEfficiencyRatio, disp: efficiencyRatio, formula: "Human Cost / AI Cost", src: "DPI-LS Engine", resource: "Calculation", dec: 2 },''')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

