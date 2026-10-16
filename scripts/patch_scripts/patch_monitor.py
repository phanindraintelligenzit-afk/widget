import re

with open('dpi_ls/monitor.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('run_llmguard_metrics, run_rebuff_metrics, run_trulens_metrics, ', '')

c = re.sub(r'^\s*llmguard_res = run_llmguard_metrics\(agent_answer\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*rebuff_res = run_rebuff_metrics\(agent_answer\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*trulens_res = run_trulens_metrics\(agent_answer\)\n', '', c, flags=re.MULTILINE)

c = re.sub(r'^\s*push_risk_results_to_backend\(collector.agent_id, llmguard_res, "LLMGuard", host_domain, port_num\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*push_risk_results_to_backend\(collector.agent_id, rebuff_res, "Rebuff", host_domain, port_num\)\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*push_risk_results_to_backend\(collector.agent_id, trulens_res, "TruLens", host_domain, port_num\)\n', '', c, flags=re.MULTILINE)

c = c.replace('push_enterprise_quality_results_to_backend(deepeval_res, trulens_res, host_domain, port_num)', 'push_enterprise_quality_results_to_backend(deepeval_res, host_domain, port_num)')

with open('dpi_ls/monitor.py', 'w', encoding='utf-8') as f:
    f.write(c)

