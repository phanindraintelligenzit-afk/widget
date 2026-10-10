file_path = 'engine/score.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_composite = '''def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    powers: dict[str, float] | None = None,
    multipliers: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
    
    # Normalize weights so they sum to 1.0, just in case
    w_sum = sum(w.values()) if w else 1.0
    norm_w = {k: (v / w_sum) for k, v in w.items()} if w_sum > 0 else DEFAULT_WEIGHTS
    
    m = {k: (v if v is not None else 0.0) for k, v in metrics.items()}
    
    # Default Powers
    default_powers = {'P': 1.0, 'Q': 1.5, 'E': 1.0, 'G': 1.5, 'R': 2.0, 'C': 1.0, 'V': 1.0}
    p = powers or default_powers
    for k in default_powers:
        if k not in p:
            p[k] = default_powers[k]
            
    # Default Multipliers
    mult = multipliers or {}
    for k in default_powers:
        if k not in mult:
            mult[k] = 1.0

    # User's exact mathematical formula with weights applied as multipliers:
    # DPI-LS = (W_P * M_P * P ** P_P) * (W_Q * M_Q * Q ** P_Q) ...
    
    term1 = (norm_w.get('P', 0) * mult['P'] * (m.get('P', 0) ** p['P'])) * \\
            (norm_w.get('Q', 0) * mult['Q'] * (m.get('Q', 0) ** p['Q'])) * \\
            (norm_w.get('E', 0) * mult['E'] * (m.get('E', 0) ** p['E']))
            
    term2 = (norm_w.get('G', 0) * mult['G'] * (m.get('G', 0) ** p['G'])) * \\
            (norm_w.get('R', 0) * mult['R'] * (m.get('R', 0) ** p['R']))
            
    term3 = (norm_w.get('C', 0) * mult['C'] * (m.get('C', 0) ** p['C'])) * \\
            (norm_w.get('V', 0) * mult['V'] * (m.get('V', 0) ** p['V']))
            
    raw_product = term1 * term2 * term3
    
    # Calculate max possible product (assuming all inputs P, Q, E... are 1.0)
    max_term1 = (norm_w.get('P', 0) * mult['P'] * (1.0 ** p['P'])) * \\
                (norm_w.get('Q', 0) * mult['Q'] * (1.0 ** p['Q'])) * \\
                (norm_w.get('E', 0) * mult['E'] * (1.0 ** p['E']))
                
    max_term2 = (norm_w.get('G', 0) * mult['G'] * (1.0 ** p['G'])) * \\
                (norm_w.get('R', 0) * mult['R'] * (1.0 ** p['R']))
                
    max_term3 = (norm_w.get('C', 0) * mult['C'] * (1.0 ** p['C'])) * \\
                (norm_w.get('V', 0) * mult['V'] * (1.0 ** p['V']))
                
    max_product = max_term1 * max_term2 * max_term3
    
    # Normalize to 100
    if max_product > 0:
        raw = (raw_product / max_product) * 100.0
    else:
        raw = 0.0
    '''

import re
# Replace the old composite function body
content = re.sub(r'def composite\(.*?\n    raw = term1 \* term2 \* term3 \* 100\.0  # Scale the base 1\.0 product up to 100 as per Implementation Plan\n    ', new_composite, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
