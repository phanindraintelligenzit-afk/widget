import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace("['prompt_cost', 'completion_cost', 'model_cost']", "['prompt_cost', 'completion_cost', 'model_cost', 'human_cost', 'ai_cost_per_output']")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

