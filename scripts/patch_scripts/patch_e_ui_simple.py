import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Add to calculateExecutionMetrics
c = c.replace(
    'otel_status:        { val: sub.otel_status       || "Unavailable", calc: sub.otel_status       || "Unavailable", disp: sub.otel_status       || "Unavailable", formula: "OpenTelemetry Export Status",          src: "OpenTelemetry (runtime telemetry)", resource: "OpenTelemetry", dec: 0 },\n      };',
    'otel_status:        { val: sub.otel_status       || "Unavailable", calc: sub.otel_status       || "Unavailable", disp: sub.otel_status       || "Unavailable", formula: "OpenTelemetry Export Status",          src: "OpenTelemetry (runtime telemetry)", resource: "OpenTelemetry", dec: 0 },\n        jaeger_trace:       { val: sub.jaeger_trace      || "Unavailable", calc: sub.jaeger_trace      || "Unavailable", disp: sub.jaeger_trace      || "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger (runtime telemetry)",        resource: "Jaeger",        dec: 0 },\n      };'
)

# Add to METRIC_LABELS if it exists or create it
if 'const METRIC_LABELS' not in c:
    pass # METRIC_NICE_NAMES might be used instead
else:
    c = c.replace(
        'otel_status: "OTel Status",\n      };',
        'otel_status: "OTel Status",\n        jaeger_trace: "Jaeger Trace",\n      };'
    )

if 'const METRIC_NICE_NAMES =' in c:
    # Look for it inside renderExecutionTableHtml
    c = c.replace(
        'otel_status: "OTel Status"\n      };',
        'otel_status: "OTel Status",\n        jaeger_trace: "Jaeger Trace"\n      };'
    )

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

