import re

with open('widget/resources.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add missing metadata
missing_meta = """
  'Guardrails AI': {
    name: 'Guardrails AI', icon: '🛡️', category: 'Validation', dpi_status: 'primary',
    description: 'Structural validation and schema enforcement.',
    dashboard_url: 'https://www.guardrailsai.com/docs', dashboard_label: 'Open Guardrails',
    sdk: 'guardrails-ai'
  },
  'Pydantic AI': {
    name: 'Pydantic AI', icon: '✨', category: 'Validation', dpi_status: 'primary',
    description: 'Type-safe parsing and validation.',
    dashboard_url: 'https://ai.pydantic.dev', dashboard_label: 'Open Pydantic AI',
    sdk: 'pydantic-ai'
  },
  'Instructor': {
    name: 'Instructor', icon: '🎓', category: 'Validation', dpi_status: 'primary',
    description: 'Structured output validation for LLMs.',
    dashboard_url: 'https://python.useinstructor.com', dashboard_label: 'Open Instructor',
    sdk: 'instructor'
  },
"""
if 'Guardrails AI' not in content:
    content = content.replace('const RESOURCE_META = {', 'const RESOURCE_META = {\n' + missing_meta)

# Update resource lists to match EXACTLY what user requested:
# cost  => langfuse, grafna and prometheous openlit,opencost
content = re.sub(r'const costResources = \[.*?\];', 'const costResources = ["Langfuse", "Grafana", "Prometheus", "OpenLIT", "OpenCost"];', content)
# validations =>deep eveal, jaeger, Zipkin , gurdails, pydanetic, useinstructor
content = re.sub(r'const valResources = \[.*?\];', 'const valResources = ["DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"];', content)
# quality=>langsmith, ragas, and agentops, confident, truelens
content = re.sub(r'const qualResources = \[.*?\];', 'const qualResources = ["LangSmith", "Ragas", "AgentOps", "DeepEval", "TruLens"];', content)
# productivity=>opentelementry, apache skywalking, and workflow layer, langfuse ,prometheous
content = re.sub(r'const prodResources = \[.*?\];', 'const prodResources = ["OpenTelemetry", "Apache SkyWalking", "Langfuse", "Prometheus"];', content)
# executions=>Langfuse, phenoix, traceloop
content = re.sub(r'const execResources = \[.*?\];', 'const execResources = ["Langfuse", "Phoenix", "Traceloop"];', content)
# risk=> rebuff, llmguard and trulens
content = re.sub(r'const riskResources = \[.*?\];', 'const riskResources = ["Rebuff", "LLMGuard", "TruLens"];', content)
# governance=> detect secrets, microsoft presidio, and open policy agents. 
content = re.sub(r'const govResources = \[.*?\];', 'const govResources = ["Detect-Secrets", "Microsoft Presidio", "Open Policy Agent"];', content)

with open('widget/resources.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched lists.')
