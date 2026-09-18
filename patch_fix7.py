import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

content = content.replace("    s: Session = Depends(db_session),\n, current_user", "    s: Session = Depends(db_session),\n    current_user")

app_path.write_text(content, encoding='utf-8')
