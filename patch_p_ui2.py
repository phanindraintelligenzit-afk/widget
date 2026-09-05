import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

target = r'''          <div style="display:grid;grid-template-columns:repeat\(3,1fr\);gap:10px;margin-bottom:10px;">
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">AI Output \(Completed\)</div>
              <div style="color:#38bdf8;font-size:18px;font-weight:800;">\$\{fmt\(metricsMap\.completed_tasks\.val, 0\)\}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Normalization \([\s\S]*?\)</div>
              <div style="color:#facc15;font-size:18px;font-weight:800;">\$\{fmt\(metricsMap\.normalization_factor\.val, 3\)\}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Human Baseline</div>
              <div style="color:#38bdf8;font-size:18px;font-weight:800;">\$\{fmt\(metricsMap\.human_baseline\.val, 1\)\}</div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:repeat\(2,1fr\);gap:10px;margin-bottom:12px;">
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Productivity Score</div>
              <div style="color:#38bdf8;font-size:18px;font-weight:800;">\$\{pScoreVal\.toFixed\(4\)\}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted \([\s\S]*?15%\)</div>
              <div style="color:#4ade80;font-size:18px;font-weight:800;">\$\{finalWeightedVal\}</div>
            </div>
          </div>

          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1\.4;">P = min\(1\.0, \(AI Output [\s\S]*?\) / Human Baseline\)</div>
          </div>
        </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-top:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>AI Output \(Completed\) : \$\{metricsMap\.completed_tasks\.val\}</div>
              <div>Normalization \([\s\S]*?\) : \$\{metricsMap\.normalization_factor\.val\}</div>
              <div>Human Baseline : \$\{metricsMap\.human_baseline\.val\}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min\(1\.0, \(\$\{metricsMap\.completed_tasks\.val\} \* \$\{metricsMap\.normalization_factor\.val\}\) / \$\{metricsMap\.human_baseline\.val == 0 \? 1 : metricsMap\.human_baseline\.val\}\) = \$\{pScoreVal\.toFixed\(4\)\}</div>
            </div>
          </div>'''

replacement = '''          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
              <div style="color:#38bdf8;font-size:18px;font-weight:800;">${pScoreVal.toFixed(4)}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (15%)</div>
              <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
              <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">P = min(1.0, (AI Output * \u03b3) / Human Baseline)</div>
            </div>
          </div>

          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>AI Output (Completed) : ${metricsMap.completed_tasks.val}</div>
              <div>Normalization (\u03b3) : ${metricsMap.normalization_factor.val}</div>
              <div>Human Baseline : ${metricsMap.human_baseline.val}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min(1.0, (${metricsMap.completed_tasks.val} * ${metricsMap.normalization_factor.val}) / ${metricsMap.human_baseline.val == 0 ? 1 : metricsMap.human_baseline.val}) = ${pScoreVal.toFixed(4)}</div>
            </div>
          </div>
        </div>'''

c = re.sub(target, replacement, c)
with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
