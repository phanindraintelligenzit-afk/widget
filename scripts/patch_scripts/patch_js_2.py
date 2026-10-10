import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''    let eScoreValToUse = value !== undefined && value !== null ? value : metricsMap.eScoreVal;
    let overlayText = (eScoreValToUse !== metricsMap.eScoreVal) ? ` (Overlay applied -> ${eScoreValToUse.toFixed(3)})` : "";
    
    let html = `
      <div style="margin-bottom:20px;font-family:'Segoe UI',Roboto,sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
          <div style="flex:1;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Execution Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>Total Attempts : ${attempts}</div>
              <div>Successful Attempts : ${successful}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Execution Score : ${successful} / ${attempts === 0 ? 1 : attempts} = ${metricsMap.eScoreVal.toFixed(3)}${overlayText}</div>
            </div>
          </div>
        </div>'''

c = re.sub(r'''          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Execution Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>Total Attempts : \$\{attempts\}</div>
              <div>Successful Attempts : \$\{successful\}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Execution Score : \$\{successful\} / \$\{attempts\} = \$\{eScoreVal\.toFixed\(3\)\}</div>
            </div>
          </div>
        </div>''', replacement, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
