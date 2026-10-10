import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

keys_to_remove = [
    'trace_id', 'span_count', 'latency', 'execution_time', 'dependencies', 'request_duration', 'error_count', 'validation_traces',
    'trace_timeline', 'span_timeline', 'service_calls', 'request_path', 'trace_latency', 'execution_timeline', 'error_timeline'
]

# We must be careful because 'trace_id' might be used for other things too, like E (Execution) has trace_id (Langfuse Trace ID).
# Wait, look at E section:
# trace_id: { val: sub.trace_id || "Unavailable", ... src: "Langfuse (runtime telemetry)" }
# So if we just remove ALL trace_id, we break E.
# Let's target the exact lines for Jaeger and Zipkin in V (Validation).

c = re.sub(r'^\s*trace_id:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*span_count:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*latency:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*execution_time:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*dependencies:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*request_duration:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*error_count:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*validation_traces:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)

c = re.sub(r'^\s*trace_timeline:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*span_timeline:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*service_calls:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*request_path:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*trace_latency:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*execution_timeline:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*error_timeline:\s*\{.*?resource:\s*"Zipkin".*?\}(,?)\n', '', c, flags=re.MULTILINE)

# Also there's jaeger_trace in E (Execution) which we should remove.
c = re.sub(r'^\s*jaeger_trace:\s*\{.*?resource:\s*"Jaeger".*?\}(,?)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*jaeger_trace:\s*".*?"(,?)\n', '', c, flags=re.MULTILINE)

# Remove knownResources Zipkin and Jaeger
c = c.replace('"Jaeger", "Zipkin", ', '')
c = c.replace('"Jaeger", ', '')
c = c.replace('"Zipkin", ', '')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

