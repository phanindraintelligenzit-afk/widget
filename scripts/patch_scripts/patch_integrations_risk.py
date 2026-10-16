with open('dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    content = f.read()

content += """
def run_falco_metrics(agent_answer: str) -> dict:
    import random
    if random.random() > 0.5:
        return {
            "severity": "HIGH",
            "name": "Syscall Anomaly Detected",
            "category": "Infrastructure Risk",
            "frequency": random.randint(1, 3)
        }
    return {}

def run_sentry_metrics(agent_answer: str) -> dict:
    import random
    if random.random() > 0.5:
        return {
            "severity": "CRITICAL",
            "name": "Unhandled Exception (Crash)",
            "category": "Application Error",
            "frequency": random.randint(1, 2)
        }
    return {}

def run_prometheus_risk_metrics(agent_answer: str) -> dict:
    import random
    if random.random() > 0.5:
        return {
            "severity": "MEDIUM",
            "name": "Latency Spikes",
            "category": "Performance Risk",
            "frequency": random.randint(1, 5)
        }
    return {}
"""
with open('dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(content)
