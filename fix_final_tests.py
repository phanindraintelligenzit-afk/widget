import re

for test_file in ['tests/test_browser_e2e.py', 'tests/test_browser_ui.py']:
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace Save & Continue with Submit Onboarding
    content = content.replace("page.click(\"button:has-text('Save & Continue')\")", "page.click(\"button:has-text('Submit Onboarding')\")")
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(content)

with open('tests/test_execution_worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the agent_id fixture
new_fixture = '''@pytest.fixture()
def agent_id(client) -> str:
    """Create a test agent owned by alice."""
    from store.repo import upsert_agent
    from api.app import get_session_factory
    aid = f"exec-test-{uuid.uuid4().hex[:8]}"
    with get_session_factory()() as s:
        upsert_agent(s, aid, "Exec Test Agent", baseline=1.0, owner_id="alice")
        s.commit()
    return aid
'''
content = re.sub(r'@pytest\.fixture\(\)\s*def agent_id\(client\) -> str:.*?(?=\n# -)', new_fixture, content, flags=re.DOTALL)

with open('tests/test_execution_worker.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed UI tests and execution test")
