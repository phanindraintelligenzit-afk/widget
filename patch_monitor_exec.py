import re

with open('dpi_ls/monitor.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(', setup_phoenix_tracing', '')
c = c.replace('run_langfuse_metrics, run_phoenix_metrics, run_traceloop_metrics', 'run_langfuse_metrics')
c = c.replace('setup_phoenix_tracing(agent_id)', '')
c = re.sub(r'^\s*phoenix_res = run_phoenix_metrics\(collector\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*traceloop_res = run_traceloop_metrics\(collector\)\n', '', c, flags=re.MULTILINE)
c = c.replace('push_execution_results_to_backend(langfuse_res, phoenix_res, traceloop_res, host_domain, port_num)', 'push_execution_results_to_backend(langfuse_res, host_domain, port_num)')

with open('dpi_ls/monitor.py', 'w', encoding='utf-8') as f:
    f.write(c)

