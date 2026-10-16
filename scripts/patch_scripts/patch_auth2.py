import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

old_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> AgentSummary:
    row = repo.upsert_agent(s, body.agent_id, body.agent_name, baseline=body.baseline_human_output)'''
new_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> AgentSummary:
    row = repo.upsert_agent(s, body.agent_id, body.agent_name, baseline=body.baseline_human_output, owner_id=current_user["username"])'''
content = content.replace(old_create, new_create)

app_path.write_text(content, encoding='utf-8')
