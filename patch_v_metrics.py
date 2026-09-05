import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace the calculateValidationMetrics body to compute dynamically
# Target to replace:
# const req = sub["Required Components"] !== undefined ? sub["Required Components"] : 0;
# const val = sub["Validated Components"] !== undefined ? sub["Validated Components"] : 0;
# let calcVScore = 0;
# if (req > 0) {
#   calcVScore = Math.min(1.0, val / req);
# }
# const vScoreVal = calcVScore;

new_logic = """
      const validationFields = [
        "answer_relevancy", "faithfulness", "hallucination", "correctness",
        "structural_validation", "schema_enforcement", "guardrails_passed", "guardrails_failed",
        "type_safe_parsing", "validation_errors", "schema_validation",
        "structured_output_validation", "schema_mapping", "instructor_passed"
      ];

      let req = 0;
      let val = 0;

      for (const field of validationFields) {
        const fieldVal = sub[field];
        if (fieldVal !== undefined && fieldVal !== null) {
          req++; 
          if (fieldVal === "Unavailable" || fieldVal === "") {
            // Not validated
          } else if (fieldVal === "0" || fieldVal === 0 || fieldVal === "0.0" || fieldVal === 0.0) {
            // If it's 0 for hallucination, validation_errors, guardrails_failed, that is a GOOD thing!
            if (["hallucination", "validation_errors", "guardrails_failed"].includes(field)) {
                val++;
            }
          } else if (["Active", "Validated", "Success", "True"].includes(fieldVal)) {
            val++;
          } else {
            const num = parseFloat(fieldVal);
            if (!isNaN(num) && num > 0) {
              val++;
            }
          }
        }
      }

      if (req === 0) {
        req = 14;
      }

      let calcVScore = 0;
      if (req > 0) {
        calcVScore = Math.min(1.0, val / req);
      }
      const vScoreVal = calcVScore;
"""

c = re.sub(
    r'const req = sub\["Required Components"\] !== undefined \? sub\["Required Components"\] : 0;\s*const val = sub\["Validated Components"\] !== undefined \? sub\["Validated Components"\] : 0;\s*let calcVScore = 0;\s*if \(req > 0\) \{\s*calcVScore = Math\.min\(1\.0, val / req\);\s*\}\s*const vScoreVal = calcVScore;',
    new_logic,
    c
)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

