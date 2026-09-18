import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

# Helper function
auth_helper = '''
def check_agent_ownership(agent_id: str, s: Session, current_user: dict):
    if current_user["role"] == "ADMIN":
        return
    agent = s.get(store.models.AgentRow, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id and agent.owner_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this agent")
'''
if 'def check_agent_ownership' not in content:
    idx = content.find('def create_agent')
    content = content[:idx] + auth_helper + '\n' + content[idx:]

# Update create_agent
old_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session)) -> AgentSummary:'''
new_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> AgentSummary:'''
content = content.replace(old_create, new_create)

# We also need to actually save the owner_id inside create_agent.
# Let's replace the whole create_agent function body for the relevant part
create_agent_body_old = '''    agent = store.models.AgentRow(
        id=body.agent_id,
        name=body.agent_name,
        status="ACTIVE"
    )
    s.add(agent)'''

create_agent_body_new = '''    agent = store.models.AgentRow(
        id=body.agent_id,
        name=body.agent_name,
        status="ACTIVE",
        owner_id=current_user["username"]
    )
    s.add(agent)'''
content = content.replace(create_agent_body_old, create_agent_body_new)

app_path.write_text(content, encoding='utf-8')
