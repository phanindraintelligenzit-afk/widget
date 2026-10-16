with open('dpi_ls/productivity_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('allowed = ["Langfuse", "OpenTelemetry", "Apache SkyWalking", "Workflow Layer"]', 'allowed = ["Langfuse", "OpenTelemetry", "Apache SkyWalking"]')
c = c.replace('"Apache SkyWalking": ["task_throughput", "worker_activity", "success_rate", "failure_rate"],\n            "Workflow Layer": ["completed_tasks", "assigned_tasks", "failed_tasks"]', '"Apache SkyWalking": ["task_throughput", "worker_activity", "success_rate", "failure_rate"]')

c = c.replace('("Langfuse", True, True, False, True),\n            (True, True, False, True),\n            ("OpenTelemetry", True, True, False, True),\n            ("Apache SkyWalking", True, True, False, True),\n            ("Workflow Layer", True, True, False, True),', '("Langfuse", True, True, False, True),\n            ("OpenTelemetry", True, True, False, True),\n            ("Apache SkyWalking", True, True, False, True),')

c = c.replace('"Apache SkyWalking": ["skywalking"],\n            "Workflow Layer": ["asyncio"],', '"Apache SkyWalking": ["skywalking"],')

c = c.replace('real_values = {"Langfuse": {}, : {}}', 'real_values = {"Langfuse": {}, "OpenTelemetry": {}, "Apache SkyWalking": {}}')

c = c.replace('"Langfuse": ["task_throughput", "latency", "execution_duration", "worker_activity", "concurrency", "success_rate", "failure_rate", "trace_count", "prompt_executions", "token_usage"],\n        }', '"Langfuse": ["task_throughput", "latency", "execution_duration", "worker_activity", "concurrency", "success_rate", "failure_rate", "trace_count", "prompt_executions", "token_usage"],\n            "OpenTelemetry": ["trace_count", "latency", "execution_duration", "concurrency"],\n            "Apache SkyWalking": ["task_throughput", "worker_activity", "success_rate", "failure_rate"]\n        }')

with open('dpi_ls/productivity_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
