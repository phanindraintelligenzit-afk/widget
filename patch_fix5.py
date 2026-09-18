import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

bad_injection = '''@app.post("/api/agents", response_model=AgentSummary)

def check_agent_ownership(agent_id: str, s: Session, current_user: dict):
    if current_user["role"] == "ADMIN":
        return
    agent = s.get(store.models.AgentRow, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id and agent.owner_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this agent")
'''

if bad_injection in content:
    content = content.replace(bad_injection, '@app.post("/api/agents", response_model=AgentSummary)\n')

    # Put it at the top level properly
    new_helper = '''
def check_agent_ownership(agent_id: str, s: Session, current_user: dict):
    if current_user["role"] == "ADMIN":
        return
    agent = s.get(store.models.AgentRow, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id and agent.owner_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this agent")
'''
    
    # inject after get_current_user
    content = content.replace("def get_current_user(token: str = Depends(oauth2_scheme)):", new_helper + "\ndef get_current_user(token: str = Depends(oauth2_scheme)):")
    app_path.write_text(content, encoding='utf-8')
    print("Fixed injection!")
else:
    print("Could not find bad injection.")
