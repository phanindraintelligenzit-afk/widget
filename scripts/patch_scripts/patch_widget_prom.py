with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'const sentry = resources["Sentry"] || {};',
    'const sentry = resources["Sentry"] || {};\n    const prometheus = resources["Prometheus"] || {};'
)

content = content.replace(
    '       metricsMap["Sentry Crash-Free Sessions"] = { val: sentry["Crash-Free Sessions"] || 0, calc: sentry["Crash-Free Sessions"] || 0, disp: sentry["Crash-Free Sessions"] || 0, formula: "Sentry Telemetry", src: "Sentry", resource: "Sentry", dec: 0 };\n    }',
    '       metricsMap["Sentry Crash-Free Sessions"] = { val: sentry["Crash-Free Sessions"] || 0, calc: sentry["Crash-Free Sessions"] || 0, disp: sentry["Crash-Free Sessions"] || 0, formula: "Sentry Telemetry", src: "Sentry", resource: "Sentry", dec: 0 };\n    }\n    if (Object.keys(prometheus).length > 0) {\n       metricsMap["Prometheus High CPU"] = { val: prometheus["High CPU"] || 0, calc: prometheus["High CPU"] || 0, disp: prometheus["High CPU"] || 0, formula: "Prometheus Telemetry", src: "Workflow Layer", resource: "Workflow Layer", dec: 0 };\n       metricsMap["Prometheus Latency Spikes"] = { val: prometheus["Latency Spikes"] || 0, calc: prometheus["Latency Spikes"] || 0, disp: prometheus["Latency Spikes"] || 0, formula: "Prometheus Telemetry", src: "Workflow Layer", resource: "Workflow Layer", dec: 0 };\n    }'
)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(content)
