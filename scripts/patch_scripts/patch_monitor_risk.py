with open('dpi_ls/monitor.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '        # Risk Evaluation',
    '        # Risk Evaluation\n        from dpi_ls.integrations import run_falco_metrics, run_sentry_metrics, run_prometheus_risk_metrics\n        falco_res = run_falco_metrics(agent_answer)\n        sentry_res = run_sentry_metrics(agent_answer)\n        prom_res = run_prometheus_risk_metrics(agent_answer)\n        if falco_res: push_risk_results_to_backend(collector.agent_id, falco_res, "Falco", host_domain, port_num)\n        if sentry_res: push_risk_results_to_backend(collector.agent_id, sentry_res, "Sentry", host_domain, port_num)\n        if prom_res: push_risk_results_to_backend(collector.agent_id, prom_res, "Prometheus", host_domain, port_num)'
)

with open('dpi_ls/monitor.py', 'w', encoding='utf-8') as f:
    f.write(content)
