import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

target = r'''        otel_status:        \{ val: sub\.otel_status       \|\| "Unavailable", calc: sub\.otel_status       \|\| "Unavailable", disp: sub\.otel_status       \|\| "Unavailable", formula: "OpenTelemetry Export Status",          src: "OpenTelemetry \(runtime telemetry\)", resource: "OpenTelemetry", dec: 0 \},
      \};'''

replacement = '''        otel_status:        { val: sub.otel_status       || "Unavailable", calc: sub.otel_status       || "Unavailable", disp: sub.otel_status       || "Unavailable", formula: "OpenTelemetry Export Status",          src: "OpenTelemetry (runtime telemetry)", resource: "OpenTelemetry", dec: 0 },
        jaeger_trace:       { val: sub.jaeger_trace      || "Unavailable", calc: sub.jaeger_trace      || "Unavailable", disp: sub.jaeger_trace      || "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger (runtime telemetry)",        resource: "Jaeger",        dec: 0 },
      };'''

c = re.sub(target, replacement, c)

target2 = r'''      const METRIC_LABELS = \{
        trace_captured: "Trace Captured",
        trace_id: "Trace ID",
        trace_status: "Trace Status",
        otel_span_count: "OTel Span Count",
        otel_status: "OTel Status",
      \};'''

replacement2 = '''      const METRIC_LABELS = {
        trace_captured: "Trace Captured",
        trace_id: "Trace ID",
        trace_status: "Trace Status",
        otel_span_count: "OTel Span Count",
        otel_status: "OTel Status",
        jaeger_trace: "Jaeger Trace",
      };'''

c = re.sub(target2, replacement2, c)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
