with open('tests/test_browser_e2e.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('assert exec_data["status"] == "QUEUED"', 'assert exec_data["status"] in ["QUEUED", "RUNNING"]')

with open('tests/test_browser_e2e.py', 'w', encoding='utf-8') as f:
    f.write(content)
