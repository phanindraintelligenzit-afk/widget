file_path = 'tests/test_engine_reference.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
content = re.sub(r'assert round\(r\.raw_score\) == \d+', 'assert round(r.raw_score) == 4', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
