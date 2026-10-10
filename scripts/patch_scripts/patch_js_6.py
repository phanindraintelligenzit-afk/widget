import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''    let rawQScore = sub.Quality_Score_Calc ? (0.7 * sub.Quality_Score_Calc.acc + 0.2 * sub.Quality_Score_Calc.cons + 0.1 * (1 - sub.Quality_Score_Calc.hall)) : 0.0;
    let qScoreValToUse = (value !== undefined && value !== null) ? value : rawQScore;
    let overlayText = (qScoreValToUse !== rawQScore) ? ` (Overlay applied -> ${typeof qScoreValToUse === 'number' ? qScoreValToUse.toFixed(3) : qScoreValToUse})` : "";

    let html = `
      <div style="margin-bottom:20px;font-family:'Segoe UI',Roboto,sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
          <div style="flex:1;">
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-top:12px;margin-bottom:12px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Quality Calculation</div>
              <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
                <div>Accuracy : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.acc.toFixed(3) : "0.000"}</div>
                <div>Consistency : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.cons.toFixed(3) : "0.000"}</div>
                <div>Hallucination : ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.hall.toFixed(3) : "0.000"}</div>
                <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Quality Score : 0.7*${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.acc.toFixed(3) : "0.000"} + 0.2*${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.cons.toFixed(3) : "0.000"} + 0.1*(1 - ${sub.Quality_Score_Calc ? sub.Quality_Score_Calc.hall.toFixed(3) : "0.000"}) = ${rawQScore.toFixed(3)}${overlayText}</div>
              </div>
            </div>
        </div>'''

c = re.sub(r'''            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;margin-top:12px;margin-bottom:12px;">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Quality Calculation</div>
              <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
                <div>Accuracy : \$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.acc\.toFixed\(3\) : "0\.000"\}</div>
                <div>Consistency : \$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.cons\.toFixed\(3\) : "0\.000"\}</div>
                <div>Hallucination : \$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.hall\.toFixed\(3\) : "0\.000"\}</div>
                <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Quality Score : 0\.7\*\$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.acc\.toFixed\(3\) : "0\.000"\} \+ 0\.2\*\$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.cons\.toFixed\(3\) : "0\.000"\} \+ 0\.1\*\(1 - \$\{sub\.Quality_Score_Calc \? sub\.Quality_Score_Calc\.hall\.toFixed\(3\) : "0\.000"\}\) = \$\{qScoreVal\}</div>
              </div>
            </div>
        </div>''', replacement, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
