import re
from pathlib import Path

test_path = Path('tests/test_dpi_ls_end_to_end.py')
content = test_path.read_text(encoding='utf-8')

content = content.replace('rating = r.json()', 'rating = r.json()\n    print(f"DEBUG RATING: {rating}")\n    if r.status_code != 200: print(f"DEBUG STATUS: {r.status_code}")')
test_path.write_text(content, encoding='utf-8')
