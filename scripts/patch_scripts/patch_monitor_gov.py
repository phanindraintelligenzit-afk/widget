import re

with open('dpi_ls/monitor.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('run_opa_metrics, run_presidio_metrics, run_detect_secrets_metrics,', 'run_opa_metrics, run_detect_secrets_metrics,')
c = re.sub(r'^\s*presidio_res = run_presidio_metrics\(agent_answer\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*push_governance_results_to_backend\(collector\.agent_id, presidio_res, "Microsoft Presidio", host_domain, port_num\)\n', '', c, flags=re.MULTILINE)

with open('dpi_ls/monitor.py', 'w', encoding='utf-8') as f:
    f.write(c)

