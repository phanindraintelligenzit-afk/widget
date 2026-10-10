import re

with open('tests/test_task1.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add onboarding insertion to the test setup
new_setup = '''
    with get_session_factory()() as s:
        upsert_agent(s, "agent-task1", "Task 1 Agent")
        from store.models import AgentOnboardingRow
        s.add(AgentOnboardingRow(agent_id="agent-task1", business_owner_email="mgr@test.com"))
        s.commit()
'''
content = re.sub(r'with get_session_factory\(\)\(\) as s:\s*upsert_agent\(s, "agent-task1", "Task 1 Agent"\)\s*s\.commit\(\)', new_setup, content)

with open('tests/test_task1.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed test_task1.py")
