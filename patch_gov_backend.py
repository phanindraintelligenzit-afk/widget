import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Fallback for total_actions and policy_violations if DB telemetry is completely zero
target = r'''    if total_actions <= 0:
        g_formula_output = 1.0 if policy_violations == 0 else 0.0
    else:
        g_formula_output = max(0.0, 1.0 - \(policy_violations / total_actions\))'''

replacement = r'''    # Fallback to initial observation values if no live DB telemetry exists
    if total_actions == 0 and policy_violations == 0:
        total_actions = sub_metrics.get("G", {}).get("total_actions", 0)
        policy_violations = len(sub_metrics.get("G", {}).get("violations", []))

    if total_actions <= 0:
        g_formula_output = 1.0 if policy_violations == 0 else 0.0
    else:
        g_formula_output = max(0.0, 1.0 - (policy_violations / total_actions))'''

c = re.sub(target, replacement, c)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

