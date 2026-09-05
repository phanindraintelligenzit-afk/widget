import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Quality active_resources
c = c.replace('"LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"', '"LangSmith", "Ragas", "AgentOps", "Confident AI"')

# Remove from list_latest_risk_resource_evaluations
c = c.replace('if r.name == "LLMGuard":\n            url = os.environ.get("LLMGUARD_URL", "#")\n            out[r.name] = {"url": url, "online": _is_reachable_global(url)}\n        elif r.name == "TruLens":\n            url = os.environ.get("TRULENS_URL", "#")\n            out[r.name] = {"url": url, "online": _is_reachable_global(url)}\n        elif r.name == "Rebuff":\n            url = os.environ.get("REBUFF_URL", "#")\n            out[r.name] = {"url": url, "online": _is_reachable_global(url)}\n        elif r.name == "Falco":', 'if r.name == "Falco":')

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
