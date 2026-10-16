import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''    let rawVScore = req > 0 ? val / req : 0.0;
    let vScoreValToUse = (value !== undefined && value !== null) ? value : rawVScore;
    let overlayText = (vScoreValToUse !== rawVScore) ? ` (Overlay applied -> ${typeof vScoreValToUse === 'number' ? vScoreValToUse.toFixed(3) : vScoreValToUse})` : "";
    
    let html = `
      <div style="margin-bottom:20px;font-family:'Segoe UI',Roboto,sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
          <div style="flex:1;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Validation Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>Required Components : ${req}</div>
              ${breakdownHtml}
              <div>Validated Components : ${val}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Validation Score : ${val} / ${req} = ${rawVScore.toFixed(3)}${overlayText}</div>
            </div>
            ${gateHtml}
          </div>
        </div>'''

c = re.sub(r'''          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Validation Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>Required Components : \$\{req\}</div>
              \$\{breakdownHtml\}
              <div>Validated Components : \$\{val\}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Validation Score : \$\{val\} / \$\{req\} = \$\{vScoreVal\.toFixed\(3\)\}</div>
            </div>
            \$\{gateHtml\}
          </div>
        </div>''', replacement, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
