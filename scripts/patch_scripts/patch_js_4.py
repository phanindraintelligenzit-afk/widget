import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''    let rawPScore = Math.min(1.0, (metricsMap.completed_tasks.val * metricsMap.normalization_factor.val) / (metricsMap.human_baseline.val == 0 ? 1 : metricsMap.human_baseline.val));
    let pScoreValToUse = (value !== undefined && value !== null) ? value : rawPScore;
    let overlayText = (pScoreValToUse !== rawPScore) ? ` (Overlay applied -> ${pScoreValToUse.toFixed(4)})` : "";
    
    let html = `
      <div style="margin-bottom:20px;font-family:'Segoe UI',Roboto,sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
          <div style="flex:1;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>AI Output (Completed) : ${metricsMap.completed_tasks.val}</div>
              <div>Normalization (I3) : ${metricsMap.normalization_factor.val}</div>
              <div>Human Baseline : ${metricsMap.human_baseline.val}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min(1.0, (${metricsMap.completed_tasks.val} * ${metricsMap.normalization_factor.val}) / ${metricsMap.human_baseline.val == 0 ? 1 : metricsMap.human_baseline.val}) = ${rawPScore.toFixed(4)}${overlayText}</div>
            </div>
          </div>
        </div>'''

c = re.sub(r'''          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>AI Output \(Completed\) : \$\{metricsMap\.completed_tasks\.val\}</div>
              <div>Normalization \(I3\) : \$\{metricsMap\.normalization_factor\.val\}</div>
              <div>Human Baseline : \$\{metricsMap\.human_baseline\.val\}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min\(1\.0, \(\$\{metricsMap\.completed_tasks\.val\} \* \$\{metricsMap\.normalization_factor\.val\}\) / \$\{metricsMap\.human_baseline\.val == 0 \? 1 : metricsMap\.human_baseline\.val\}\) = \$\{pScoreVal\.toFixed\(4\)\}</div>
            </div>
          </div>
        </div>''', replacement, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
