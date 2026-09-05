import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

new_logic = """
        res["V"] = {}
        res = enrich_validation_sub_metrics(s, res)

        validation_fields = [
            "answer_relevancy", "faithfulness", "hallucination", "correctness",
            "structural_validation", "schema_enforcement", "guardrails_passed", "guardrails_failed",
            "type_safe_parsing", "validation_errors", "schema_validation",
            "structured_output_validation", "schema_mapping", "instructor_passed"
        ]

        req = 0
        val = 0
        v_sub = res["V"]

        for field in validation_fields:
            field_val = v_sub.get(field)
            if field_val is not None:
                req += 1
                if field_val in ("Unavailable", ""):
                    pass
                elif field_val in ("0", 0, "0.0", 0.0):
                    if field in ("hallucination", "validation_errors", "guardrails_failed"):
                        val += 1
                elif field_val in ("Active", "Validated", "Success", "True"):
                    val += 1
                else:
                    try:
                        num = float(field_val)
                        if num > 0:
                            val += 1
                    except (ValueError, TypeError):
                        pass

        if req == 0:
            req = 14

        v_score = (val / req) * 100 if req > 0 else 0

        res["V"]["Required Components"] = req
        res["V"]["Validated Components"] = val
        res["V"]["Validation Score"] = v_score
"""

pattern = r'req = 0\s*val = 0\s*eval_map = \{\}\s*if s is not None:\s*evals = repo\.list_latest_validation_resource_evaluations\(s\)\s*eval_map = \{f"\{r\.resource_name\}:\{r\.metric\}": r\.current_value for r in evals\}\s*for r in evals:\s*if not r\.metric\.endswith\("_evidence"\):\s*req \+= 1\s*if r\.status == "SUCCESS":\s*val \+= 1\s*# Fallback to static if no runtime evaluations exist \(e\.g\., tests without bootstrap\)\s*if req == 0:\s*req = v_raw\.get\("required_components"\) or 6\s*val = v_raw\.get\("validated_components"\) or 0\s*v_score = \(val / max\(req, 1\)\) \* 100\s*res\["V"\] = \{\s*"Required Components": req,\s*"Validated Components": val,\s*"Validation Score": v_score,\s*\}\s*res = enrich_validation_sub_metrics\(s, res\)'

c = re.sub(pattern, new_logic, c)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

