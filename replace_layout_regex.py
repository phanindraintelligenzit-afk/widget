import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

pattern = r'<div style="display:grid;grid-template-columns:repeat\(3,1fr\);gap:10px;margin-bottom:10px;">.*?<div\s+style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>'

new_block = '''<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
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
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Productivity Calculation</div>'''

c, count = re.subn(pattern, new_block, c, flags=re.DOTALL)
if count > 0:
    print("Replaced successfully!")
    with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
        f.write(c)
else:
    print("Failed to replace!")
