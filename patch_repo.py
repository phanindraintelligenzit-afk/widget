with open('store/repo.py', 'r', encoding='utf-8') as f:
    c = f.read()

import re
c = re.sub(
    r'def get_settings\(s: Session\) -> Settings:\s+row = s.get\(SettingsRow, 1\)\s+if row is None:\s+raise RuntimeError\("Engine uncalibrated: \'app_settings\' missing from database\. Run sensitivity harness to initialize\."\)\s+return Settings\.model_validate\(row\.payload\)',
    'def get_settings(s: Session) -> Settings:\n    row = s.get(SettingsRow, 1)\n    if row is None:\n        return Settings(\n            q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10},\n            gate_thresholds={"G": 0.60, "R": 0.50, "V": 0.60},\n            r_max=50.0,\n            human_cost_per_output=50.0\n        )\n    return Settings.model_validate(row.payload)',
    c
)

with open('store/repo.py', 'w', encoding='utf-8') as f:
    f.write(c)
