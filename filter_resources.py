import re

keep_names = {
    'Langfuse', 'OpenCost', 'OpenLIT',
    'DeepEval', 'Guardrails AI', 'Pydantic AI', 'Instructor',
    'Ragas', 'AgentOps',
    'OpenTelemetry', 'Apache SkyWalking',
    'Jaeger',
    'Open Policy Agent', 'Keycloak', 'OpenMetadata',
    'Falco', 'Sentry', 'Prometheus'
}

with open('widget/resources.html', 'r', encoding='utf-8') as f:
    content = f.read()

# First we need to parse out the RESOURCE_META block.
start_idx = content.find('const RESOURCE_META = {')
end_idx = content.find('const STATUS_ORDER =')

meta_block = content[start_idx:end_idx]

for name in [
    'Grafana', 'Zipkin', 'TruLens', 'Confident AI', 'LangSmith', 
    'Workflow Layer', 'Phoenix', 'Traceloop', 'LLMGuard', 'Rebuff', 
    'Detect-Secrets', 'Microsoft Presidio', 'Tempo'
]:
    # Regex to match 'Name': { ... }, or "Name": { ... },
    pattern = r"['\"]" + name + r"['\"]\s*:\s*\{[^\}]*\},\s*"
    meta_block = re.sub(pattern, '', meta_block)

content = content[:start_idx] + meta_block + content[end_idx:]

# Also remove from DOCS
for name in [
    'Grafana', 'Zipkin', 'TruLens', 'Confident AI', 'LangSmith', 
    'Workflow Layer', 'Phoenix', 'Traceloop', 'LLMGuard', 'Rebuff', 
    'Detect-Secrets', 'Microsoft Presidio', 'Tempo'
]:
    pattern2 = r"['\"]" + name + r"['\"]\s*:\s*[\"'].*?[\"'],?\s*"
    content = re.sub(pattern2, '', content)

with open('widget/resources.html', 'w', encoding='utf-8') as f:
    f.write(content)
