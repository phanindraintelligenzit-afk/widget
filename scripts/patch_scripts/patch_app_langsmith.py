import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('"LangSmith", "Ragas", "AgentOps", "Confident AI"', '"Ragas", "AgentOps", "DeepEval"')

c = re.sub(r'^\s*langsmith_url = .*?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"LangSmith": .*?\n', '', c, flags=re.MULTILINE)

c = re.sub(r'@app\.post\("/api/quality-evaluation/push-langsmith"\)\ndef push_langsmith_results[\s\S]*?return {"updated": updated, "count": len\(updated\)}\n', '', c)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)

