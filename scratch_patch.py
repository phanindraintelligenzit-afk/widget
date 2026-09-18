import sys

with open('api/app.py', 'a', encoding='utf-8') as f:
    f.write('\n@app.post("/agents/{agent_id}/execute")\n')
    f.write('def execute_agent(agent_id: str):\n')
    f.write('    return {"status": "executing", "agent_id": agent_id}\n')
