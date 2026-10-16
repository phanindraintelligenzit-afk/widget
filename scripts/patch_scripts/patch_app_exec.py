import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('"Langfuse", "Phoenix", "Traceloop"', '"Langfuse"')

# Remove URLs from get_execution_evaluation_urls
c = re.sub(r'^\s*phoenix_collector = .*?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*phoenix_url = .*?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*traceloop_url = .*?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Phoenix": .*?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*"Traceloop": .*?\n', '', c, flags=re.MULTILINE)

# Remove push endpoints
c = re.sub(r'@app\.post\("/api/execution-evaluation/push-phoenix"\)\ndef push_phoenix_results[\s\S]*?return {"updated": updated, "count": len\(updated\)}\n', '', c)
c = re.sub(r'@app\.post\("/api/execution-evaluation/push-traceloop"\)\ndef push_traceloop_results[\s\S]*?return {"updated": updated, "count": len\(updated\)}\n', '', c)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)

