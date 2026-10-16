import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Replace calculateQualityMetrics logic
old_q_logic = r'''    const accuracy = sub\.semantic_accuracy \|\| "Unavailable";
    const consistency = sub\.consistency_measurement \|\| "Unavailable";
    const hallucination = sub\.hallucination_analysis \|\| "Unavailable";
    
    let qScoreVal = "Pending SME Review";
    if \(value !== undefined && value !== null && value !== "Pending SME Review"\) \{
      qScoreVal = value;
    \}'''

new_q_logic = '''    let accVal = 0;
    if (sub.semantic_accuracy && sub.semantic_accuracy !== "Unavailable") accVal = parseFloat(sub.semantic_accuracy);
    else if (sub.correctness && sub.correctness !== "Unavailable") accVal = parseFloat(sub.correctness);
    if (isNaN(accVal)) accVal = 0;

    let consVal = 0;
    if (sub.consistency_measurement && sub.consistency_measurement !== "Unavailable") consVal = parseFloat(sub.consistency_measurement);
    else if (sub.consistency && sub.consistency !== "Unavailable") consVal = parseFloat(sub.consistency);
    if (isNaN(consVal)) consVal = 0;

    let hallVal = 0;
    if (sub.hallucination && sub.hallucination !== "Unavailable") hallVal = parseFloat(sub.hallucination);
    if (isNaN(hallVal)) hallVal = 0;

    let calcQ = (0.7 * accVal) + (0.2 * consVal) + (0.1 * (1.0 - hallVal));
    let qScoreVal = calcQ.toFixed(4);
    
    sub.Quality_Score_Calc = { acc: accVal, cons: consVal, hall: hallVal };
'''

c = re.sub(old_q_logic, new_q_logic, c)

# 2. Add the Calculation block HTML in renderQualityTableHtml
old_html_return = r'''    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
      <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
      <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Q = 0.7\*Accuracy \+ 0.2\*Consistency \+ 0.1\*\(1 - Hallucination\)</div>
    </div>
  </div>
</div>'''

new_html_return = r'''    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
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

c = re.sub(old_html_return, new_html_return, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
