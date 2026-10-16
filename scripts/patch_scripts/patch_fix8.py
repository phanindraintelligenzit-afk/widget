import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

# Fix duplicate current_user in update_agent and delete_agent
content = re.sub(
    r"(def (?:update_agent|delete_agent)\(.*?current_user:\s*dict\s*=\s*Depends\(require_role\(\[\"ADMIN\"\]\)\)),\s*current_user:\s*dict\s*=\s*Depends\(get_current_user\)",
    r"\1",
    content,
    flags=re.DOTALL
)

app_path.write_text(content, encoding='utf-8')
