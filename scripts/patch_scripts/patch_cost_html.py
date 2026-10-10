import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

html_block = '''
      const utilVal = parseFloat(sub.utilization) || parseFloat(settings.utilization) || 1.0;
      const aiCostVal = metricsMap.ai_cost_per_output ? fmt(metricsMap.ai_cost_per_output.calc, 4) : "Unavailable";
      
      const formulaBlock = 
        <div style="margin-bottom:20px;padding:15px;background:#1e293b;border:1px solid #334155;border-radius:6px;font-family:'Courier New',Courier,monospace;">
          <div style="font-size:12px;color:#94a3b8;margin-bottom:8px;font-weight:bold;">COST DIMENSION FORMULA</div>
          <div style="font-size:14px;color:#f8fafc;margin-bottom:12px;background:#0f172a;padding:8px;border-radius:4px;">C = min(1, AI Cost per Output / Human Cost per Output) &times; Utilization Factor</div>
          <div style="display:flex;gap:24px;font-size:13px;flex-wrap:wrap;">
            <div style="background:#0f172a;padding:6px 12px;border-radius:4px;"><span style="color:#64748b;">Human Cost:</span> <span style="color:#22c55e;font-weight:bold;">.00</span></div>
            <div style="background:#0f172a;padding:6px 12px;border-radius:4px;"><span style="color:#64748b;">AI Cost/Output:</span> <span style="color:#facc15;font-weight:bold;">$&#36;{aiCostVal}</span></div>
            <div style="background:#0f172a;padding:6px 12px;border-radius:4px;"><span style="color:#64748b;">Utilization:</span> <span style="color:#38bdf8;font-weight:bold;">&#36;{utilVal}</span></div>
          </div>
        </div>
      ;

      return 
        <div class="cost-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:&#36;{resourceFilter ? '8px' : '0 0 8px 8px'};">
          &#36;{resourceFilter ? '' : formulaBlock}
'''

c = re.sub(r'return \s*<div class="cost-table-wrapper" style="padding:20px;background:#090d16;font-family:\'Courier New\',Courier,monospace;border:1px solid #334155;border-radius:\$\{resourceFilter \? \'8px\' : \'0 0 8px 8px\'\};">', html_block, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

