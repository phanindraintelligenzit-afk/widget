import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Currently it looks like:
#          </div>
#        </div>
#        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
#          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>
#            <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
#              <div>AI Output (Completed) : ${metricsMap.completed_tasks.val}</div>
#              <div>Normalization (?) : ${metricsMap.normalization_factor.val}</div>
#              <div>Human Baseline : ${metricsMap.human_baseline.val}</div>
#              <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Productivity Score : min(1.0, (${metricsMap.completed_tasks.val} * ${metricsMap.normalization_factor.val}) / ${metricsMap.human_baseline.val == 0 ? 1 : metricsMap.human_baseline.val}) = ${pScoreVal.toFixed(4)}</div>
#            </div>
#          </div>

pattern = r'</div>\s*</div>\s*<div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">\s*<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>'

new_block = '''</div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>'''

c, count = re.subn(pattern, new_block, c)

if count > 0:
    print("Fixed closing tag!")
else:
    print("Closing tag fix failed!")
    
# We also need to add the closing tag back AFTER the calculation block!
# Let's find the end of the calculation block.
pattern2 = r'=\s*\$\{pScoreVal\.toFixed\(4\)\}</div>\s*</div>\s*</div>\s*<div class="productivity-table-wrapper"'
new_block2 = '''= ${pScoreVal.toFixed(4)}</div>
            </div>
          </div>
        </div>
        <div class="productivity-table-wrapper"'''

c, count2 = re.subn(pattern2, new_block2, c)

if count2 > 0:
    print("Fixed wrapper close!")
else:
    print("Wrapper close fix failed!")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
