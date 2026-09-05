import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

target1 = r'          jaeger_trace:       \{ val: sub\.jaeger_trace      \|\| "Unavailable", calc: sub\.jaeger_trace      \|\| "Unavailable", disp: sub\.jaeger_trace      \|\| "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger \(runtime telemetry\)",        resource: "Jaeger",        dec: 0 \},'
replacement1 = r'''          jaeger_trace:       { val: sub.jaeger_trace      || "Unavailable", calc: sub.jaeger_trace      || "Unavailable", disp: sub.jaeger_trace      || "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger (runtime telemetry)",        resource: "Jaeger",        dec: 0 },
        Total_Attempts:     { val: attempts, calc: attempts, disp: attempts, formula: "", src: "", resource: "Execution Engine", dec: 0 },
        Successful_Attempts:{ val: successful, calc: successful, disp: successful, formula: "", src: "", resource: "Execution Engine", dec: 0 },
        Execution_Score:    { val: calcEScore, calc: calcEScore, disp: calcEScore, formula: "", src: "", resource: "Execution Engine", dec: 3 },'''

c, count = re.subn(target1, replacement1, c)

if count > 0:
    print("Replaced metricsMap successfully!")
else:
    print("Failed to replace metricsMap!")

# Update renderExecutionTableHtml to filter them out
target2 = r'entries = entries\.filter\(\(\[_, m\]\) => m\.val !== "Unavailable"\);'
replacement2 = r'entries = entries.filter(([key, m]) => m.val !== "Unavailable" && !["Total_Attempts", "Successful_Attempts", "Execution_Score"].includes(key));'

c, count2 = re.subn(target2, replacement2, c)

if count2 > 0:
    print("Replaced renderExecutionTableHtml filter successfully!")
else:
    print("Failed to replace renderExecutionTableHtml filter!")

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)
