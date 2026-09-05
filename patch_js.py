import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

replacement = r'''    // Raw Governance value from the official formula (telemetry only).
    let formulaOutput;
    if (totalActions <= 0) {
      formulaOutput = policyViolations === 0 ? 1.0 : 0.0;
    } else {
      formulaOutput = Math.max(0.0, 1.0 - (policyViolations / totalActions));
    }

    // The engine-derived value (when supplied) is authoritative for the
    // displayed Raw / Weighted numbers; fall back to the formula calc.
    let gScoreVal = (value === undefined || value === null) ? formulaOutput : value;'''

c = re.sub(r'''    // Raw Governance value from the official formula \(telemetry only\)\.
    let gScoreVal;
    if \(totalActions <= 0\) {
      gScoreVal = policyViolations === 0 \? 1\.0 : 0\.0;
    } else {
      gScoreVal = Math\.max\(0\.0, 1\.0 - \(policyViolations / totalActions\)\);
    }

    // The engine-derived value \(when supplied\) is authoritative for the
    // displayed Raw / Weighted numbers; fall back to the formula calc\.
    if \(value === undefined \|\| value === null\) value = gScoreVal;
    else gScoreVal = value;''', replacement, c)

c = c.replace('Governance Score : 1 - (${policyViolations} / ${totalActions}) = ${gScoreVal.toFixed(3)}', 'Governance Score : 1 - (${policyViolations} / ${totalActions}) = ${formulaOutput.toFixed(3)}' + (
    '${gScoreVal !== formulaOutput ? ` (Overlay applied -> ${gScoreVal.toFixed(3)})` : ""}'
))

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
