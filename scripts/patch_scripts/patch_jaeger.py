import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Add jaeger_trace to the return block of calculateExecutionMetrics
pattern = r'(otel_status:.*?\},)(?=\s*\};\s*\}\s*function renderExecutionTableHtml)'
replacement = r'\1\n        jaeger_trace:       { val: sub.jaeger_trace      || "Unavailable", calc: sub.jaeger_trace      || "Unavailable", disp: sub.jaeger_trace      || "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger (runtime telemetry)",        resource: "Jaeger",        dec: 0 },'
c = re.sub(pattern, replacement, c, flags=re.DOTALL)

# Add jaeger_trace to METRIC_NICE_NAMES in renderExecutionTableHtml
pattern2 = r'(otel_status: "OTel Status",)(?=\s*\};\s*let entries = Object\.entries\(metricsMap\);)'
replacement2 = r'\1\n        jaeger_trace: "Jaeger Trace",'
c = re.sub(pattern2, replacement2, c, flags=re.DOTALL)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

