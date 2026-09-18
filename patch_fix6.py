import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

content = content.replace("check_agent_ownership(agent_id, s, current_user)", "")

app_path.write_text(content, encoding='utf-8')
