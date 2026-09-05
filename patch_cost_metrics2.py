import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace val/disp bindings for AI Cost Per Output and Efficiency Ratio to strictly use the dynamic ones
c = c.replace('ai_cost_per_output: { val: aiCostPerOutput, calc: calcAiCostPerOutput, disp: aiCostPerOutput', 'ai_cost_per_output: { val: calcAiCostPerOutput, calc: calcAiCostPerOutput, disp: calcAiCostPerOutput')
c = c.replace('efficiency_ratio: { val: efficiencyRatio, calc: calcEfficiencyRatio, disp: efficiencyRatio', 'efficiency_ratio: { val: calcEfficiencyRatio, calc: calcEfficiencyRatio, disp: calcEfficiencyRatio')

# I will also add human_cost, ai_cost_per_output, efficiency_ratio to METRIC_NICE_NAMES
nice_names_addition = """
        human_cost: "Human Cost",
        ai_cost_per_output: "AI Cost Per Output",
        efficiency_ratio: "Efficiency Ratio",
"""
c = c.replace('model_cost: "Model Cost",', 'model_cost: "Model Cost",\n' + nice_names_addition)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

