with open('api/scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '    sentry = {"Exception Rate": 0, "Crash-Free Sessions": 0, "Unhandled Exceptions": 0, "Issues": 0}\n',
    '    sentry = {"Exception Rate": 0, "Crash-Free Sessions": 0, "Unhandled Exceptions": 0, "Issues": 0}\n    prometheus = {"High CPU": 0, "Memory Leaks": 0, "Latency Spikes": 0, "Error Anomalies": 0}\n'
)

content = content.replace(
    '        elif src == "Sentry":\n            if "exception" in inc["name"].lower() or "error" in inc["name"].lower(): sentry["Unhandled Exceptions"] += inc["frequency"]\n            elif "crash" in inc["name"].lower(): sentry["Crash-Free Sessions"] += inc["frequency"]\n            elif "rate" in inc["name"].lower(): sentry["Exception Rate"] += inc["frequency"]\n            else: sentry["Issues"] += inc["frequency"]\n',
    '        elif src == "Sentry":\n            if "exception" in inc["name"].lower() or "error" in inc["name"].lower(): sentry["Unhandled Exceptions"] += inc["frequency"]\n            elif "crash" in inc["name"].lower(): sentry["Crash-Free Sessions"] += inc["frequency"]\n            elif "rate" in inc["name"].lower(): sentry["Exception Rate"] += inc["frequency"]\n            else: sentry["Issues"] += inc["frequency"]\n        elif src == "Prometheus":\n            if "cpu" in inc["name"].lower(): prometheus["High CPU"] += inc["frequency"]\n            elif "memory" in inc["name"].lower(): prometheus["Memory Leaks"] += inc["frequency"]\n            elif "latency" in inc["name"].lower(): prometheus["Latency Spikes"] += inc["frequency"]\n            else: prometheus["Error Anomalies"] += inc["frequency"]\n'
)

content = content.replace(
    '            "Sentry": sentry\n        }\n',
    '            "Sentry": sentry,\n            "Prometheus": prometheus\n        }\n'
)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
