import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace using regex for flexibility with whitespace
html_block = '''</div>
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Cost Calculation</div>
<div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
<div>Human Cost per Output : .00</div>
<div>AI Cost per Output : {metricsMap.ai_cost_per_output ? fmt(metricsMap.ai_cost_per_output.calc, 4) : '0.0000'}</div>
<div>Utilization Factor : </div>
<div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Cost Score : min(1, {metricsMap.ai_cost_per_output ? fmt(metricsMap.ai_cost_per_output.calc, 4) : '0.0000'} / .00) *  = </div>
</div>
</div>
</div>
'''

pattern = r'</div>\s*</div>\s*</div>\s*<div class="cost-table-wrapper"'
c = re.sub(pattern, html_block + '\n<div class="cost-table-wrapper"', c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
