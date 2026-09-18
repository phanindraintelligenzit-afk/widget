import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

content = content.replace("if isinstance(value, (dict, list), current_user: dict = Depends(get_current_user)):", "if isinstance(value, (dict, list)):")

app_path.write_text(content, encoding='utf-8')
