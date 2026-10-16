file_path = 'api/scoring.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We will inject a helper to fetch custom powers/multipliers
helper = '''
def _get_custom_formula_configs(s, agent_id: str):
    powers = {}
    multipliers = {}
    if s:
        try:
            from store import repo
            configs = repo.list_agent_configurations(s, agent_id)
            for c in configs:
                key = c.configuration_key
                val = float(c.configuration_value)
                if key.startswith("Power_"):
                    powers[key.replace("Power_", "")] = val
                elif key.startswith("Multiplier_"):
                    multipliers[key.replace("Multiplier_", "")] = val
        except Exception:
            pass
    return powers, multipliers
'''

# Find a good place to insert the helper
idx = content.find("def score_and_persist")
content = content[:idx] + helper + "\n" + content[idx:]

# Now replace the rate() calls
old_call1 = '''    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )'''

new_call1 = '''    powers, multipliers = _get_custom_formula_configs(s, obs.agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
        powers=powers,
        multipliers=multipliers,
    )'''

content = content.replace(old_call1, new_call1)

old_call2 = '''    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )'''

new_call2 = '''    powers, multipliers = _get_custom_formula_configs(s, agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
        powers=powers,
        multipliers=multipliers,
    )'''

# Because replace replaced both above if I just used replace, I need to do it correctly.
# Wait, they are exactly the same string.
# But for the first one I need obs.agent_id, and for the second one I need gent_id.
# This requires a more targeted replace.
