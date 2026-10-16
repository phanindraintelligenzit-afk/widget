file_path = 'engine/rate.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_rate = '''def rate(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    gate_thresholds: dict[str, float] | None = None,
    min_dimensions_for_full_band: int = 4,
) -> Rating:'''

new_rate = '''def rate(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    gate_thresholds: dict[str, float] | None = None,
    min_dimensions_for_full_band: int = 4,
    powers: dict[str, float] | None = None,
    multipliers: dict[str, float] | None = None,
) -> Rating:'''

content = content.replace(old_rate, new_rate)

old_composite_call = '''    # 1. Composite ?" DPI-LS formula and linear weighted metrics.
    raw, weighted_metrics, weights_used = composite(metrics, weights)'''

new_composite_call = '''    # 1. Composite ?" DPI-LS formula and linear weighted metrics.
    raw, weighted_metrics, weights_used = composite(metrics, weights, powers, multipliers)'''

# Using regex replace because of unicode characters in the comment string
import re
content = re.sub(r'raw, weighted_metrics, weights_used = composite\(metrics, weights\)', 'raw, weighted_metrics, weights_used = composite(metrics, weights, powers, multipliers)', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
