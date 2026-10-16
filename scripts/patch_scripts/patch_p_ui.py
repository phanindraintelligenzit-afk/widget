import re
with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

target = r'(<div style="color:#e2e8f0;font-size:11px;line-height:1\.4;">P = min\(1\.0, \(AI Output \* \xce\xb3\) / Human Baseline\)</div>\s*</div>\s*</div>)'
match = re.search(target, c)

if not match:
    # Try a different target string
    target2 = 'P = min(1.0, (AI Output \xc3\x97 \xce\xb3) / Human Baseline)</div>\n            </div>\n          </div>'
    if target2 in c:
        pass
    else:
        # Fallback to finding "Human Baseline" logic and searching up
        print("Regex match failed")

# The exact HTML from earlier:
# <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">P = min(1.0, (AI Output \xc3\x97 \xce\xb3) / Human Baseline)</div>

pattern = r'(<div style="color:#e2e8f0;font-size:11px;line-height:1\.4;">P = min\(1\.0, \(AI Output [^)]*\) / Human Baseline\)</div>\s*</div>\s*</div>)'
match = re.search(pattern, c)
if match:
    repl = match.group(1) + '''
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-top:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
              <div>AI Output (Completed) : ${metricsMap.completed_tasks.val}</div>
              <div>Normalization (\u03b3) : ${metricsMap.normalization_factor.val}</div>
              <div>Human Baseline : ${metricsMap.human_baseline.val}</div>
              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min(1.0, (${metricsMap.completed_tasks.val} * ${metricsMap.normalization_factor.val}) / ${metricsMap.human_baseline.val == 0 ? 1 : metricsMap.human_baseline.val}) = ${pScoreVal.toFixed(4)}</div>
            </div>
          </div>'''
    c = c[:match.start()] + repl + c[match.end():]
    print("Productivity calculation injected successfully.")
else:
    print("Failed to find injection point.")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

