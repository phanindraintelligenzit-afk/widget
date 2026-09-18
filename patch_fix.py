import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

# Fix the syntax error in list_all_agents
content = content.replace("for agent, score in repo.latest_scores_for_all(s, current_user: dict = Depends(get_current_user)):", "for agent, score in repo.latest_scores_for_all(s):")

app_path.write_text(content, encoding='utf-8')
