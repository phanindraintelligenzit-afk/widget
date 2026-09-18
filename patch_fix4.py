import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

content = content.replace("def agent_profile_page(, current_user: dict = Depends(get_current_user)):", "def agent_profile_page(request: Request, agent_id: str):")
content = content.replace("def delete_agent(agent_id: str, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):", "def delete_agent(agent_id: str, s: Session = Depends(db_session)):")
content = content.replace("def delete_agent(, current_user: dict = Depends(get_current_user)):", "def delete_agent(agent_id: str, s: Session = Depends(db_session)):")

app_path.write_text(content, encoding='utf-8')
