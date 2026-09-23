file_path = 'api/app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Restore Auth for score_preview
content = re.sub(
    r'async def score_preview\(agent_id: str, request: Request, s: Session = Depends\(db_session\)\):',
    r'async def score_preview(agent_id: str, request: Request, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):',
    content
)

# Restore Auth for configure_agent
content = re.sub(
    r'async def configure_agent\(agent_id: str, config: AgentConfigurationIn, s: Session = Depends\(db_session\)\):',
    r'async def configure_agent(agent_id: str, config: AgentConfigurationIn, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):',
    content
)

# Restore created_by attribution
content = re.sub(
    r'created_by="Admin"',
    r'created_by=current_user.get("username", "System")',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
