file_path = 'engine/score.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# I will just write a new script that replaces from 'def composite' to the end of the file.
new_code = '''def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    powers: dict[str, float] | None = None,
    multipliers: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
    
    w_sum = sum(w.values()) if w else 1.0
    norm_w = {k: (v / w_sum) for k, v in w.items()} if w_sum > 0 else DEFAULT_WEIGHTS
    
    m = {k: (v if v is not None else 0.0) for k, v in metrics.items()}
    
    default_powers = {'P': 1.0, 'Q': 1.5, 'E': 1.0, 'G': 1.5, 'R': 2.0, 'C': 1.0, 'V': 1.0}
    p = powers or default_powers
    for k in default_powers:
        if k not in p:
            p[k] = default_powers[k]
            
    mult = multipliers or {}
    for k in default_powers:
        if k not in mult:
            mult[k] = 1.0

    term_P = norm_w.get('P', 0) * mult['P'] * (m.get('P', 0) ** p['P'])
    term_Q = norm_w.get('Q', 0) * mult['Q'] * (m.get('Q', 0) ** p['Q'])
    term_E = norm_w.get('E', 0) * mult['E'] * (m.get('E', 0) ** p['E'])
    term_G = norm_w.get('G', 0) * mult['G'] * (m.get('G', 0) ** p['G'])
    term_R = norm_w.get('R', 0) * mult['R'] * (m.get('R', 0) ** p['R'])
    term_C = norm_w.get('C', 0) * mult['C'] * (m.get('C', 0) ** p['C'])
    term_V = norm_w.get('V', 0) * mult['V'] * (m.get('V', 0) ** p['V'])
    
    raw_sum = term_P + term_Q + term_E + term_G + term_R + term_C + term_V
    
    max_sum = (norm_w.get('P', 0) * mult['P']) + \\
              (norm_w.get('Q', 0) * mult['Q']) + \\
              (norm_w.get('E', 0) * mult['E']) + \\
              (norm_w.get('G', 0) * mult['G']) + \\
              (norm_w.get('R', 0) * mult['R']) + \\
              (norm_w.get('C', 0) * mult['C']) + \\
              (norm_w.get('V', 0) * mult['V'])
                
    if max_sum > 0:
        raw = (raw_sum / max_sum) * 100.0
    else:
        raw = 0.0
        
    term1 = term_P + term_Q + term_E
    term2 = term_G + term_R
    term3 = term_C + term_V
    
    present = {k: v for k, v in metrics.items() if v is not None}
    if not present:
        return raw, {}, {}

    total_weight = sum(w.get(k, 0) for k in present)
    if total_weight <= 0:
        active_weights = {}
        weighted_metrics = {k: 0.0 for k in m}
    else:
        active_weights = {k: w.get(k, 0) / total_weight for k in present}
        weighted_metrics = {k: active_weights[k] * float(v) for k, v in present.items()}
    
    weighted_metrics["term1"] = term1
    weighted_metrics["term2"] = term2
    weighted_metrics["term3"] = term3

    return raw, weighted_metrics, active_weights
'''

content = content[:content.find("def composite")] + new_code

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
