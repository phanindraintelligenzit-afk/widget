import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

target = r'''    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
      <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
      <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Q = 0.7\*Accuracy \+ 0.2\*Consistency \+ 0.1\*\(1 - Hallucination\)</div>
    </div>
  </div>
</div>'''

replacement = '''    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
      <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
      <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Q = 0.7*Accuracy + 0.2*Consistency + 0.1*(1 - Hallucination)</div>
    </div>
  </div>
  
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-bottom:12px;">
    <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Quality Calculation</div>
    <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
      <div>Accuracy : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.acc.toFixed(3) : "0.000"}</div>
      <div>Consistency : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.cons.toFixed(3) : "0.000"}</div>
      <div>Hallucination : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.hall.toFixed(3) : "0.000"}</div>
      <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Quality Score : 0.7*${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.acc.toFixed(3) : "0.000"} + 0.2*${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.cons.toFixed(3) : "0.000"} + 0.1*(1 - ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.hall.toFixed(3) : "0.000"}) = ${qScoreVal}</div>
    </div>
  </div>
</div>'''

c = re.sub(target, replacement, c)
with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

