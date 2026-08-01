import re

app_path = "api/app.py"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace hardcoded active_resources with correct sets
replacements = {
    r'active_resources = \{"Langfuse", "Prometheus", "Grafana", "OpenLIT", "OpenCost"\}': 
    'active_resources = {"Langfuse", "Prometheus", "Grafana", "OpenLIT", "OpenCost"}',
    
    r'active_resources = \{"DeepEval", "Jaeger", "Zipkin"\}': 
    'active_resources = {"DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"}',
    
    r'active_resources = \{"LangSmith", "Ragas", "AgentOps"\}': 
    'active_resources = {"LangSmith", "Ragas", "AgentOps", "DeepEval", "TruLens"}',
    
    r'active_resources = \{"OpenTelemetry", "Grafana Tempo", "Apache SkyWalking"\}': 
    'active_resources = {"OpenTelemetry", "Apache SkyWalking", "Langfuse", "Prometheus"}',
    
    r'active_resources = \{"Langfuse", "Phoenix", "Traceloop"\}': 
    'active_resources = {"Langfuse", "Phoenix", "Traceloop"}',
    
    r'active_resources = \{"Rebuff", "LLMGuard", "TruLens"\}': 
    'active_resources = {"Rebuff", "LLMGuard", "TruLens"}',
    
    r'active_resources = \{"Detect-Secrets", "Microsoft Presidio", "Open Policy Agent"\}': 
    'active_resources = {"Detect-Secrets", "Microsoft Presidio", "Open Policy Agent"}'
}

for pat, repl in replacements.items():
    content = re.sub(pat, repl, content)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("api/app.py patched.")

