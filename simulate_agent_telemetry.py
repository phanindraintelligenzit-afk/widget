import urllib.request
import json
import time

def post_data(endpoint, payload):
    url = f"http://127.0.0.1:8000/api/quality-evaluation/{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[{endpoint}] Response: {resp.status}")
    except Exception as e:
        print(f"[{endpoint}] Push failed: {e}")

langsmith = {
    "runtime_traces": "1",
    "llm_evaluation": "0.92",
    "hallucination_analysis": "0.05",
    "prompt_evaluation": "0.89",
    "context_evaluation": "0.88"
}

ragas = {
    "semantic_accuracy": 0.94,
    "faithfulness": 0.88,
    "answer_relevancy": 0.91,
    "context_precision": 0.90,
    "context_recall": 0.85
}

agentops = {
    "runtime_execution_history": "1",
    "agent_behaviour": "0.95",
    "consistency_measurement": "0.93",
    "session_metrics": "1",
    "stability_metrics": "0.99"
}

print("Simulating test_agent.py telemetry pushes...")
post_data("push-langsmith", langsmith)
post_data("push-ragas", ragas)
post_data("push-agentops", agentops)

# Simulate Apache SkyWalking
skywalking_payload = {
    "agent_id": "chandra-finops",
    "session_id": "test-session-123",
    "metrics": {
        "token_depth": 14,
        "throughput": 42.5
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
}
def post_skywalking(payload):
    url = "http://127.0.0.1:8000/api/productivity-evaluation/push-skywalking"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[SkyWalking] Response: {resp.status}")
    except Exception as e:
        print(f"[SkyWalking] Push failed: {e}")

post_skywalking(skywalking_payload)

# Simulate Rebuff
rebuff_payload = {
    "agent_id": "chandra-finops",
    "source_resource": "Rebuff",
    "name": "Simulated Rebuff Prompt Injection",
    "category": "Security",
    "severity": "CRITICAL",
    "frequency": 1,
    "trace_id": "trace-1234",
    "span_id": "span-1234"
}
def post_rebuff(payload):
    url = "http://127.0.0.1:8000/api/risk-evaluation/push"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[Rebuff] Response: {resp.status}")
    except Exception as e:
        print(f"[Rebuff] Push failed: {e}")

post_rebuff(rebuff_payload)

# Simulate Governance
def post_governance(payload):
    url = "http://127.0.0.1:8000/api/governance-evaluation/push"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[Governance {payload['source_resource']}] Response: {resp.status}")
    except Exception as e:
        print(f"[Governance {payload['source_resource']}] Push failed: {e}")

post_governance({
    "agent_id": "chandra-finops",
    "source_resource": "Keycloak",
    "name": "Unauthorized Access Attempt",
    "category": "Denial",
    "severity": "High",
    "frequency": 2,
    "trace_id": "trace-kc-1",
    "span_id": "span-kc-1"
})

post_governance({
    "agent_id": "chandra-finops",
    "source_resource": "OpenMetadata",
    "name": "Schema Violation",
    "category": "Violation",
    "severity": "High",
    "frequency": 1,
    "trace_id": "trace-om-1",
    "span_id": "span-om-1"
})
print("Triggering quality evaluation pipeline...")
try:
    url_quality = "http://127.0.0.1:8000/api/quality-evaluation/evaluate"
    req_quality = urllib.request.Request(url_quality, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_quality, timeout=30) as response:
        print(f"[evaluate] Response: {response.status}")
except Exception as e:
    print(f"Evaluation trigger failed: {e}")
