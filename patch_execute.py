import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_exec = '''@app.post("/agents/{agent_id}/execute")
def execute_agent(agent_id: str, s: Session = Depends(db_session)):
    import subprocess
    import os
    
    agent = s.get(store.models.AgentRow, agent_id)
    agent_name = agent.name if agent else agent_id
    
    def run_eval_thread(a_id, a_name):
        env = os.environ.copy()
        env["AGENT_ID"] = a_id
        env["AGENT_NAME"] = a_name
        env["HUMAN_BASELINE"] = "1"
        env["BEDROCK_MODEL_ID"] = "mock-model"
        env["AWS_ACCESS_KEY_ID"] = "rotated"
        env["LITELLM_DROP_PARAMS"] = "True"
        try:
            print(f"[Synchronous] Running test_agent.py for {a_id}...")
            subprocess.run(["uv", "run", "python", "examples/test_agent.py"], env=env)
        except Exception as e:
            print(f"[Synchronous] Error: {e}")
            
    run_eval_thread(agent_id, agent_name)
    
    return {"status": "executed", "agent_id": agent_id}'''

content = re.sub(
    r'@app\.post\("/agents/\{agent_id\}/execute"\)\ndef execute_agent\(agent_id: str\):\n    return \{"status": "executing", "agent_id": agent_id\}',
    new_exec,
    content
)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched api/app.py")
