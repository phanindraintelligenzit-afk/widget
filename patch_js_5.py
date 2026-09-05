import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''  let rawCostScore = Math.min(1.0, (metricsMap.ai_cost_per_output ? parseFloat(metricsMap.ai_cost_per_output.calc) : 0.0) / 200.0) * parseFloat(sub.utilization || settings.utilization || 1.0);
  let costScoreValToUse = (value !== undefined && value !== null) ? value : rawCostScore;
  let overlayText = (costScoreValToUse !== rawCostScore) ? ` (Overlay applied -> ${costScoreValToUse.toFixed(4)})` : "";

  let html = `
  <div style="margin-bottom:20px;font-family:'Segoe UI',Roboto,sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
  <div style="flex:1;">
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
  <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Cost Calculation</div>
  <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
  <div>Human Cost per Output : $200.00</div>
  <div>AI Cost per Output : $${metricsMap.ai_cost_per_output ? fmt(metricsMap.ai_cost_per_output.calc, 4) : '0.0000'}</div>
  <div>Utilization Factor : ${fmt(sub.utilization || settings.utilization || 1.0, 2)}</div>
  <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Cost Score : min(1, $${metricsMap.ai_cost_per_output ? fmt(metricsMap.ai_cost_per_output.calc, 4) : '0.0000'} / $200.00) * ${fmt(sub.utilization || settings.utilization || 1.0, 2)} = ${rawCostScore.toFixed(4)}${overlayText}</div>
  </div>
  </div>
  </div>'''

c = re.sub(r'''  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
  <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Cost Calculation</div>
  <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
  <div>Human Cost per Output : \$200\.00</div>
  <div>AI Cost per Output : \$\$\{metricsMap\.ai_cost_per_output \? fmt\(metricsMap\.ai_cost_per_output\.calc, 4\) : '0\.0000'\}</div>
  <div>Utilization Factor : \$\{fmt\(sub\.utilization \|\| settings\.utilization \|\| 1\.0, 2\)\}</div>
  <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Cost Score : min\(1, \$\$\{metricsMap\.ai_cost_per_output \? fmt\(metricsMap\.ai_cost_per_output\.calc, 4\) : '0\.0000'\} / \$200\.00\) \* \$\{fmt\(sub\.utilization \|\| settings\.utilization \|\| 1\.0, 2\)\} = \$\{costScoreVal\.toFixed\(4\)\}</div>
  </div>
  </div>
  </div>''', replacement, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
