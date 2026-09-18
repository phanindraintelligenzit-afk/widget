# -*- coding: utf-8 -*-
import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

old_test = '''@app.post("/api/agents/{agent_id}/test_connection")
async def test_connection(agent_id: str):
    return {"status": "CONNECTED", "latency_ms": 42}'''

new_test = '''@app.post("/api/agents/{agent_id}/test_connection")
async def test_connection(agent_id: str):
    # Simulated safe health check / Stub. User requirement: Do NOT return CONNECTED from a stub.
    return {"status": "BLOCKED", "error": "External credentials unavailable in current environment"}'''

content = content.replace(old_test, new_test)
app_path.write_text(content, encoding='utf-8')
