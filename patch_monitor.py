import sys

with open('d:/DPI-LS/widget/dpi_ls/monitor.py', 'r') as f:
    content = f.read()

import_old = "run_llmguard_metrics, run_rebuff_metrics, run_trulens_metrics, push_risk_results_to_backend,"
import_new = "run_llmguard_metrics, run_rebuff_metrics, run_trulens_metrics, push_risk_results_to_backend, \\\n    run_falco_metrics, run_sentry_metrics, run_prometheus_metrics,"

content = content.replace(import_old, import_new)

call_old = '''        push_risk_results_to_backend(collector.agent_id, llmguard_res, "LLMGuard", host_domain, port_num)
        push_risk_results_to_backend(collector.agent_id, rebuff_res, "Rebuff", host_domain, port_num)
        push_risk_results_to_backend(collector.agent_id, trulens_res, "TruLens", host_domain, port_num)'''

call_new = '''        push_risk_results_to_backend(collector.agent_id, llmguard_res, "LLMGuard", host_domain, port_num)
        push_risk_results_to_backend(collector.agent_id, rebuff_res, "Rebuff", host_domain, port_num)
        push_risk_results_to_backend(collector.agent_id, trulens_res, "TruLens", host_domain, port_num)
        
        run_falco_metrics(collector.agent_id)
        run_sentry_metrics(collector.agent_id)
        run_prometheus_metrics(collector.agent_id)'''

content = content.replace(call_old, call_new)

with open('d:/DPI-LS/widget/dpi_ls/monitor.py', 'w') as f:
    f.write(content)
print('Updated monitor.py')
