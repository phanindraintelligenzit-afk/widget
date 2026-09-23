file_path = 'engine/score.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Rewrite composite
old_composite = '''def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
    m = {k: (v if v is not None else 0.0) for k, v in metrics.items()}
    
    # Deck: PI = (P * Q * 1.5E) + (G * 1.5R) + (C * V)
    term1 = m.get('P', 0) * m.get('Q', 0) * 1.5 * m.get('E', 0)
    term2 = m.get('G', 0) * 1.5 * m.get('R', 0)
    term3 = m.get('C', 0) * m.get('V', 0)
    
    # Max possible is (1*1*1.5) + (1*1.5) + (1*1) = 4.0
    raw = (term1 + term2 + term3) * 25.0'''

new_composite = '''def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    powers: dict[str, float] | None = None,
    multipliers: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
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

    # User's exact mathematical formula: 
    # DPI-LS = ( (M_P * P ** P_P) * (M_Q * Q ** P_Q) * (M_E * E ** P_E) ) * 
    #          ( (M_G * G ** P_G) * (M_R * R ** P_R) ) * 
    #          (M_C * C ** P_C) * (M_V * V ** P_V)
    
    term1 = (mult['P'] * (m.get('P', 0) ** p['P'])) * (mult['Q'] * (m.get('Q', 0) ** p['Q'])) * (mult['E'] * (m.get('E', 0) ** p['E']))
    term2 = (mult['G'] * (m.get('G', 0) ** p['G'])) * (mult['R'] * (m.get('R', 0) ** p['R']))
    term3 = (mult['C'] * (m.get('C', 0) ** p['C'])) * (mult['V'] * (m.get('V', 0) ** p['V']))
    
    raw = term1 * term2 * term3 * 100.0  # Scale the base 1.0 product up to 100 as per Implementation Plan
    '''

content = content.replace(old_composite, new_composite)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
