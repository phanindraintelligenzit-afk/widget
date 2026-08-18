import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace hardcoded documentation fallbacks
fallbacks_to_remove = [
    'LLMGUARD_URL', 'TRULENS_URL', 'REBUFF_URL', 'OPENLIT_URL', 'DEEPEVAL_URL',
    'GUARDRAILS_URL', 'INSTRUCTOR_URL', 'PYDANTIC_URL', 'LANGSMITH_URL',
    'RAGAS_URL', 'AGENTOPS_URL', 'TRACELOOP_BASE_URL', 'OPA_URL',
    'PRESIDIO_URL', 'DETECT_SECRETS_URL'
]

for var in fallbacks_to_remove:
    # We replace any fallback string for these variables with "#"
    # Match os.environ.get("VAR", "ANYTHING") -> os.environ.get("VAR", "#")
    pattern = r'os\.environ\.get\([\'\"]' + var + r'[\'\"],\s*[\'\"].*?[\'\"]\)'
    repl = f'os.environ.get("{var}", "#")'
    code = re.sub(pattern, repl, code)

# Fix missing urls in risk-evaluation
risk_replacement = '''        if r.name == "LLMGuard":
            url = os.environ.get("LLMGUARD_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "TruLens":
            url = os.environ.get("TRULENS_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Rebuff":
            url = os.environ.get("REBUFF_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Falco":
            url = os.environ.get("FALCO_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Sentry":
            url = os.environ.get("SENTRY_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Prometheus":
            url = os.environ.get("PROMETHEUS_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}'''
code = re.sub(
    r'        if r\.name == "LLMGuard":.*?elif r\.name == "Rebuff":.*?_is_reachable_global\(url\)\}',
    risk_replacement,
    code,
    flags=re.DOTALL
)

# Fix missing urls in governance-evaluation
gov_replacement = '''        if r.name == "Open Policy Agent":
            url = os.environ.get("OPA_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Microsoft Presidio":
            url = os.environ.get("PRESIDIO_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Detect-Secrets":
            url = os.environ.get("DETECT_SECRETS_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "Keycloak":
            url = os.environ.get("KEYCLOAK_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}
        elif r.name == "OpenMetadata":
            url = os.environ.get("OPENMETADATA_URL", "#")
            out[r.name] = {"url": url, "online": _is_reachable_global(url)}'''
code = re.sub(
    r'        if r\.name == "Open Policy Agent":.*?elif r\.name == "Detect-Secrets":.*?_is_reachable_global\(url\)\}',
    gov_replacement,
    code,
    flags=re.DOTALL
)

# Fix missing url in productivity-evaluation
prod_replacement = '''    skywalking_ui_url = os.environ.get("SKYWALKING_UI_URL", "http://localhost:8080")
    workflow_url = os.environ.get("WORKFLOW_URL", "#")

    return {
        "OpenTelemetry":     {"url": otel_ui_url,       "online": _is_reachable_global(otel_url)},
        "Grafana Tempo":     {"url": tempo_ui_url,      "online": _is_reachable_global(tempo_url)},
        "Apache SkyWalking": {"url": skywalking_ui_url, "online": _is_reachable_global(skywalking_url)},
        "Workflow Layer":    {"url": workflow_url,      "online": _is_reachable_global(workflow_url)},
    }'''
code = re.sub(
    r'    skywalking_ui_url = os\.environ\.get\("SKYWALKING_UI_URL".*?\}',
    prod_replacement,
    code,
    flags=re.DOTALL
)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done modifying app.py')
