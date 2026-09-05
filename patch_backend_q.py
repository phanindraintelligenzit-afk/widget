import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_hall_str = 'hallucination_str = sub_metrics["Q"].get("Hallucination Rate") or q_eval_map.get("LangSmith:hallucination_analysis", "Unavailable")'
new_hall_str = 'hallucination_str = sub_metrics["Q"].get("Hallucination Rate") or q_eval_map.get("DeepEval:Hallucination Score") or q_eval_map.get("Confident AI:hallucination") or "Unavailable"'

c = c.replace(old_hall_str, new_hall_str)

import sys
if new_hall_str in c:
    print("Successfully replaced hallucination_str")
else:
    print("Failed to replace hallucination_str")

# Also need to calculate q_score dynamically
old_q_score_block = '''    try:
        if "Unavailable" not in (accuracy_str, consistency_str, hallucination_str) and "" not in (accuracy_str, consistency_str, hallucination_str):
            acc = float(accuracy_str)
            cons = float(consistency_str)
            hall = float(hallucination_str)
            q_score = (0.7 * acc) + (0.2 * cons) + (0.1 * (1.0 - hall))
            q_score = round(q_score, 4)
            status = "COMPLETED"
        else:
            q_score = sub_metrics["Q"].get("Quality Score") if sub_metrics["Q"].get("Quality Score") != "Pending SME Review" else None
            status = sub_metrics["Q"].get("Status", "Pending SME Review")
    except (ValueError, TypeError):
        q_score = None
        status = sub_metrics["Q"].get("Status", "Pending SME Review")'''

new_q_score_block = '''    try:
        acc = float(accuracy_str) if accuracy_str not in ("Unavailable", "") else 0.0
        cons = float(consistency_str) if consistency_str not in ("Unavailable", "") else 0.0
        hall = float(hallucination_str) if hallucination_str not in ("Unavailable", "") else 0.0
        
        # Determine if we have at least one valid metric
        if accuracy_str not in ("Unavailable", "") or consistency_str not in ("Unavailable", "") or hallucination_str not in ("Unavailable", ""):
            q_score = (0.7 * acc) + (0.2 * cons) + (0.1 * (1.0 - hall))
            q_score = round(q_score, 4)
            status = "COMPLETED"
        else:
            q_score = sub_metrics["Q"].get("Quality Score") if sub_metrics["Q"].get("Quality Score") != "Pending SME Review" else None
            status = sub_metrics["Q"].get("Status", "Pending SME Review")
    except (ValueError, TypeError):
        q_score = None
        status = sub_metrics["Q"].get("Status", "Pending SME Review")'''

c = c.replace(old_q_score_block, new_q_score_block)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

