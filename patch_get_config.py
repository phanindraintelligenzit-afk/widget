import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

old_get_config = '''def get_agent_configs(agent_id: str, s: Session = Depends(db_session)) -> list[AgentConfigurationOut]:
    rows = store.repo.list_agent_configurations(s, agent_id)'''

new_get_config = '''def get_agent_configs(agent_id: str, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> list[AgentConfigurationOut]:
    check_agent_ownership(agent_id, s, current_user)
    rows = store.repo.list_agent_configurations(s, agent_id)'''

content = content.replace(old_get_config, new_get_config)
app_path.write_text(content, encoding='utf-8')
