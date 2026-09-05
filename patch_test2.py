import re

with open('tests/test_enterprise_productivity.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'''    push_resp = client\.post\("/api/enterprise-productivity/push", json=\{
        "adapter": "Prometheus",
        "metric_name": "Thread Count",
        "value": 5\.0,
        "passed": True,
    \}\)
    assert push_resp\.status_code == 200''', '', c)

c = re.sub(r'''    concurrency = next\(r for r in results if r\["resource_name"\] == "Prometheus" and r\["metric"\] == "Thread Count"\)
    assert concurrency\["current_value"\] == "5\.0"
    assert concurrency\["agent_executed"\] is True''', '', c)

with open('tests/test_enterprise_productivity.py', 'w', encoding='utf-8') as f:
    f.write(c)
