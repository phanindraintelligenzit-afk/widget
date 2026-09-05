import re

with open('dpi_ls/risk_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

# metrics list
c = re.sub(r'^\s*"Prometheus": \["high_cpu_usage", "memory_leak", "latency_spike", "error_rate_anomaly"\]\n', '', c, flags=re.MULTILINE)

# incident block
block = '''        # Evaluate Prometheus
        prometheus_freq = sum(i.frequency for i in prometheus_incidents)
        has_prometheus = prometheus_freq > 0 or is_test_env
        metrics_prometheus = ["high_cpu_usage", "memory_leak", "latency_spike", "error_rate_anomaly"]
        for m in metrics_prometheus:
            save_risk_resource_evaluation(
                self.session, "Prometheus", m,
                detected=has_prometheus,
                evidence=f"{prometheus_freq} incidents detected in runtime" if has_prometheus else "No incidents",
                current_value=str(prometheus_freq),
                status="SUCCESS" if has_prometheus else "FAILED",
                dashboard_verified=has_prometheus,
                agent_executed=has_prometheus
            )'''
c = c.replace(block, '')

# incident array map
c = re.sub(r'^\s*"Prometheus": \[\n(?:\s*.*\n){1,6}\s*\],\n', '', c, flags=re.MULTILINE)

with open('dpi_ls/risk_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
