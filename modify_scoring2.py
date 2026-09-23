file_path = 'api/scoring.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

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
                try:
                    val = float(c.configuration_value)
                    if key.startswith("Power_"):
                        powers[key.replace("Power_", "")] = val
                    elif key.startswith("Multiplier_"):
                        multipliers[key.replace("Multiplier_", "")] = val
                except ValueError:
                    pass
        except Exception:
            pass
    return powers, multipliers
'''

idx = content.find("def score_and_persist")
content = content[:idx] + helper + "\n" + content[idx:]

# We need to replace the rate call inside score_and_persist:
content = content.replace('''
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    # Surface RAG signals''', 
    '''
    powers, multipliers = _get_custom_formula_configs(s, obs.agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
        powers=powers,
        multipliers=multipliers,
    )
    # Surface RAG signals''')

# We need to replace the rate call inside rescore_from_partials:
content = content.replace('''
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    rating.sub_metrics = sub_metrics''', 
    '''
    powers, multipliers = _get_custom_formula_configs(s, agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
        powers=powers,
        multipliers=multipliers,
    )
    rating.sub_metrics = sub_metrics''')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
