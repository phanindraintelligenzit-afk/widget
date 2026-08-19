import sys
import re

with open('d:/DPI-LS/widget/dpi_ls/integrations.py', 'r') as f:
    js = f.read()

js = re.sub(r'\"trace_id\": uuid\.uuid4\(\)\.hex', '\"trace_id\": \"mock-trace-id\"', js)
js = re.sub(r'\"span_id\": uuid\.uuid4\(\)\.hex\[:16\]', '\"span_id\": \"mock-span-id\"', js)
js = re.sub(r'str\(uuid\.uuid4\(\)\)', '\"mock-trace-id\"', js)

with open('d:/DPI-LS/widget/dpi_ls/integrations.py', 'w') as f:
    f.write(js)
print('Updated integrations.py to use static trace_ids for mock data')
