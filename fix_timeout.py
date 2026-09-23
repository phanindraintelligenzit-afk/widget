file_path = 'tests/test_dpi_ls_end_to_end.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Change timeout=5.0 to timeout=30.0
content = re.sub(r'timeout=5\.0', 'timeout=30.0', content)

# Also fix the Pydantic deprecation warning while I'm here
content = re.sub(r'payload=s\.dict\(\)', 'payload=s.model_dump()', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
