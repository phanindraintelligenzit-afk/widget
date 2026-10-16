import re

with open('tests/test_dynamic_weightages.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """obs = {
        "agent_id": "test-agent",
        "agent_name": "Test Agent",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }"""

text = re.sub(r'obs = \{[^{}]+\}', replacement, text, flags=re.DOTALL)
# The above regex might fail due to nested braces in the previous payload. 
# Let me just replace the specific broken test cases payload.
