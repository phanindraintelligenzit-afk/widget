with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

target = """    if total_actions <= 0:
        g_formula_output = 1.0 if policy_violations == 0 else 0.0
    else:
        g_formula_output = max(0.0, 1.0 - (policy_violations / total_actions))"""

replacement = """    if total_actions == 0 and policy_violations == 0:
        total_actions = sub_metrics.get("G", {}).get("total_actions", 0)
        
        # Count actual violations (excluding rule="none") just like in metrics_from_observation
        raw_violations = sub_metrics.get("G", {}).get("violations", [])
        policy_violations = len(set(v.get("when") for v in raw_violations if v.get("rule") and v.get("rule") != "none"))

    if total_actions <= 0:
        g_formula_output = 1.0 if policy_violations == 0 else 0.0
    else:
        g_formula_output = max(0.0, 1.0 - (policy_violations / total_actions))"""

c = c.replace(target, replacement)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

