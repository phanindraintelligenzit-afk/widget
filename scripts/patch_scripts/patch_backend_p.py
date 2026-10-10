import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_metrics_extract = '''    # Extract complexity metrics from Langfuse & Prometheus
    t_d = safe_float(p_eval_map.get("Langfuse:token_usage"), p_eval_map.get("Apache SkyWalking:token_depth"))
    a_c = safe_float(p_eval_map.get("Langfuse:prompt_executions"), p_eval_map.get("Grafana Tempo:api_calls"))
    d_b = safe_float(p_eval_map.get("Prometheus:queue_length"), p_eval_map.get("OpenTelemetry:decision_branches"))'''

new_metrics_extract = '''    # Extract complexity metrics from current resources
    t_d = safe_float(p_eval_map.get("Apache SkyWalking:token_depth"), p_eval_map.get("Langfuse:token_usage"))
    a_c = safe_float(p_eval_map.get("Langfuse:api_calls"), p_eval_map.get("Langfuse:prompt_executions"))
    d_b = safe_float(p_eval_map.get("OpenTelemetry:decision_branches"), 0.0)'''

c = c.replace(old_metrics_extract, new_metrics_extract)

old_metrics_update = '''        "token_depth": t_d,
        "api_calls": a_c,
        "decision_branches": d_b,
        "worker_concurrency": safe_float(p_eval_map.get("Prometheus:concurrency"), 1.0),
        "execution_duration": safe_float(p_eval_map.get("Langfuse:execution_duration"), 0.0),
        "throughput": safe_float(p_eval_map.get("Prometheus:throughput"), 0.0),
        "cpu_usage": safe_float(p_eval_map.get("Prometheus:cpu_usage"), 0.0),
        "memory_usage": safe_float(p_eval_map.get("Prometheus:memory_usage"), 0.0),
        "infrastructure_health": safe_float(p_eval_map.get("Prometheus:infrastructure_health"), 1.0),'''

new_metrics_update = '''        "token_depth": t_d,
        "api_calls": a_c,
        "decision_branches": d_b,
        "worker_concurrency": safe_float(p_eval_map.get("Workflow Layer:worker_concurrency"), 1.0),
        "execution_duration": safe_float(p_eval_map.get("Langfuse:execution_duration"), 0.0),
        "throughput": safe_float(p_eval_map.get("Langfuse:throughput"), 0.0),
        "cpu_usage": safe_float(p_eval_map.get("Workflow Layer:cpu_usage"), 0.0),
        "memory_usage": safe_float(p_eval_map.get("Workflow Layer:memory_usage"), 0.0),
        "infrastructure_health": safe_float(p_eval_map.get("Workflow Layer:infrastructure_health"), 1.0),'''

c = c.replace(old_metrics_update, new_metrics_update)

old_e_c_human = 'e_c_human = safe_float(p_eval_map.get("Prometheus:human_complexity"), 10.0)'
new_e_c_human = 'e_c_human = safe_float(p_eval_map.get("Workflow Layer:human_complexity"), 10.0)'

c = c.replace(old_e_c_human, new_e_c_human)

import sys
if new_metrics_extract in c and new_metrics_update in c and new_e_c_human in c:
    print("Backend productivity metrics extraction patched successfully")
else:
    print("Failed to patch backend productivity metrics")

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

