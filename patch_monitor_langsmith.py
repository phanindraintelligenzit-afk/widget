import re

with open('dpi_ls/monitor.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('run_deepeval_metrics, run_ragas, run_langsmith, run_agentops', 'run_deepeval_metrics, run_ragas, run_agentops')
c = re.sub(r'^\s*langsmith_res = run_langsmith\(\)\n', '', c, flags=re.MULTILINE)
c = c.replace('push_quality_results_to_backend(langsmith_res, ragas_res, agentops_res, host_domain, port_num)', 'push_quality_results_to_backend(ragas_res, agentops_res, host_domain, port_num)')

with open('dpi_ls/monitor.py', 'w', encoding='utf-8') as f:
    f.write(c)

