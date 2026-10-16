with open('dpi_ls/risk_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '        "Sentry": [\n            "exception_rate", "crash_free_sessions", "unhandled_exceptions", "issue_count"\n        ],',
    '        "Sentry": [\n            "exception_rate", "crash_free_sessions", "unhandled_exceptions", "issue_count"\n        ],\n        "Prometheus": [\n            "high_cpu", "memory_leaks", "latency_spikes", "error_anomalies"\n        ],'
)

content = content.replace(
    '        "Sentry": ("sentry_sdk",),',
    '        "Sentry": ("sentry_sdk",),\n        "Prometheus": ("prometheus_client",),'
)

content = content.replace(
    '            ("Sentry", True, True, False, True),',
    '            ("Sentry", True, True, False, True),\n            ("Prometheus", True, True, False, True),'
)

with open('dpi_ls/risk_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
