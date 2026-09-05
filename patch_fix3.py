import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

content = content.replace("def login_page(, current_user: dict = Depends(get_current_user)):", "def login_page():")

app_path.write_text(content, encoding='utf-8')
