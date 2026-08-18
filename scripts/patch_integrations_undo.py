import sys

with open('d:/DPI-LS/widget/dpi_ls/integrations.py', 'r', encoding='utf-8') as f:
    js = f.read()

js = js.replace('"mock-trace-id"', 'uuid.uuid4().hex')
js = js.replace('"mock-span-id"', 'uuid.uuid4().hex[:16]')

with open('d:/DPI-LS/widget/dpi_ls/integrations.py', 'w', encoding='utf-8') as f:
    f.write(js)
print('Restored UUIDs to integrations.py')
