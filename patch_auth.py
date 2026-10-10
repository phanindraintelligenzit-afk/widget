import sys

def remove_auth():
    with open('api/app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Patch 1: /onboard
    t1 = """@app.post("/api/agents/{agent_id}/onboard", response_model=AgentOnboardingOut)
def update_onboarding(agent_id: str, body: AgentOnboardingIn, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> AgentOnboardingOut:
    # Auto-create base agent if it doesn't exist
    agent = s.get(store.models.AgentRow, agent_id)
    if not agent:
        agent = store.models.AgentRow(id=agent_id, name=agent_id, owner_id=current_user["username"])
        s.add(agent)
        s.flush()
    else:
        check_agent_ownership(agent_id, s, current_user)"""
        
    r1 = """@app.post("/api/agents/{agent_id}/onboard", response_model=AgentOnboardingOut)
def update_onboarding(agent_id: str, body: AgentOnboardingIn, s: Session = Depends(db_session)) -> AgentOnboardingOut:
    # Auto-create base agent if it doesn't exist
    agent = s.get(store.models.AgentRow, agent_id)
    if not agent:
        agent = store.models.AgentRow(id=agent_id, name=agent_id, owner_id="test_user")
        s.add(agent)
        s.flush()"""

    content = content.replace(t1, r1)

    # Patch 2: /run_telemetry
    t2 = """@app.post("/api/agents/{agent_id}/run_telemetry")
def run_telemetry_endpoint(agent_id: str, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):"""
    
    r2 = """@app.post("/api/agents/{agent_id}/run_telemetry")
def run_telemetry_endpoint(agent_id: str, s: Session = Depends(db_session)):"""

    content = content.replace(t2, r2)
    
    with open('api/app.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
if __name__ == '__main__':
    remove_auth()
