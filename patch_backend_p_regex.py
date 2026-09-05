import re

with open('api/scoring.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace extraction
c = re.sub(
    r't_d = safe_float\(p_eval_map\.get\("Langfuse:token_usage"\), p_eval_map\.get\("Apache SkyWalking:token_depth"\)\)\s*a_c = safe_float\(p_eval_map\.get\("Langfuse:prompt_executions"\), p_eval_map\.get\("Grafana Tempo:api_calls"\)\)\s*d_b = safe_float\(p_eval_map\.get\("Prometheus:queue_length"\), p_eval_map\.get\("OpenTelemetry:decision_branches"\)\)',
    '''t_d = safe_float(p_eval_map.get("Apache SkyWalking:token_depth"), p_eval_map.get("Langfuse:token_usage"))
    a_c = safe_float(p_eval_map.get("Langfuse:api_calls"), p_eval_map.get("Langfuse:prompt_executions"))
    d_b = safe_float(p_eval_map.get("OpenTelemetry:decision_branches"), 0.0)''',
    c
)

# Replace update mapping
c = re.sub(r'"worker_concurrency": safe_float\(p_eval_map\.get\("Prometheus:concurrency"\), 1\.0\)', '"worker_concurrency": safe_float(p_eval_map.get("Workflow Layer:worker_concurrency"), 1.0)', c)
c = re.sub(r'"throughput": safe_float\(p_eval_map\.get\("Prometheus:throughput"\), 0\.0\)', '"throughput": safe_float(p_eval_map.get("Langfuse:throughput"), 0.0)', c)
c = re.sub(r'"cpu_usage": safe_float\(p_eval_map\.get\("Prometheus:cpu_usage"\), 0\.0\)', '"cpu_usage": safe_float(p_eval_map.get("Workflow Layer:cpu_usage"), 0.0)', c)
c = re.sub(r'"memory_usage": safe_float\(p_eval_map\.get\("Prometheus:memory_usage"\), 0\.0\)', '"memory_usage": safe_float(p_eval_map.get("Workflow Layer:memory_usage"), 0.0)', c)
c = re.sub(r'"infrastructure_health": safe_float\(p_eval_map\.get\("Prometheus:infrastructure_health"\), 1\.0\)', '"infrastructure_health": safe_float(p_eval_map.get("Workflow Layer:infrastructure_health"), 1.0)', c)
c = re.sub(r'"resolution_velocity": safe_float\(p_eval_map\.get\("Grafana Tempo:resolution_velocity"\), 0\.0\)', '"resolution_velocity": safe_float(p_eval_map.get("Langfuse:resolution_velocity"), 0.0)', c)
c = re.sub(r'e_c_human = safe_float\(p_eval_map\.get\("Prometheus:human_complexity"\), 10\.0\)', 'e_c_human = safe_float(p_eval_map.get("Workflow Layer:human_complexity"), 10.0)', c)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.write(c)

