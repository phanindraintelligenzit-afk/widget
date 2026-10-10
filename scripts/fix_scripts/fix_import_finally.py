with open('tests/test_execution_worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("from store._db import get_session_factory", "from store.db import get_session_factory")
content = content.replace("from api.app import get_session_factory", "from store.db import get_session_factory")

with open('tests/test_execution_worker.py', 'w', encoding='utf-8') as f:
    f.write(content)
