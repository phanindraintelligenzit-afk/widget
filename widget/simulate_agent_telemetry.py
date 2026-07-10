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

print("Triggering quality evaluation pipeline...")
try:
    url_quality = "http://127.0.0.1:8000/api/quality-evaluation/evaluate"
    req_quality = urllib.request.Request(url_quality, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_quality, timeout=30) as response:
        print(f"[evaluate] Response: {response.status}")
except Exception as e:
    print(f"Evaluation trigger failed: {e}")
