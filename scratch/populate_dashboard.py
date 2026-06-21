"""
Simple script to populate the main DPI-LS Dashboard (P, Q, E, G, R) with mock agent runs.
Does not require litellm or any internet access. Just uses the local API.
"""
import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

# Mock ratings for 3 different agents
MOCK_RATINGS = [
    {
        "agent_id": "chandra-finops",
        "timestamp": "2026-06-21T10:00:00Z",
        "scores": {
            "P": 0.85,
            "Q": 0.92,
            "E": 0.78,
            "G": 1.0,
            "R": 0.15
        },
        "raw_signals": {
            "latency_ms": 1200,
            "tokens_used": 1540,
            "hallucination_score": 0.05,
            "cost_usd": 0.04
        }
    },
    {
        "agent_id": "risk-evaluator",
        "timestamp": "2026-06-21T10:05:00Z",
        "scores": {
            "P": 0.95,
            "Q": 0.88,
            "E": 0.99,
            "G": 0.8,
            "R": 0.05
        },
        "raw_signals": {
            "latency_ms": 450,
            "tokens_used": 320,
            "hallucination_score": 0.01,
            "cost_usd": 0.01
        }
    },
    {
        "agent_id": "support-bot",
        "timestamp": "2026-06-21T10:10:00Z",
        "scores": {
            "P": 0.70,
            "Q": 0.75,
            "E": 0.60,
            "G": 0.5,
            "R": 0.40
        },
        "raw_signals": {
            "latency_ms": 3200,
            "tokens_used": 4500,
            "hallucination_score": 0.25,
            "cost_usd": 0.12
        }
    }
]


def post_rating(payload):
    url = f"{BASE_URL}/ingest"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        print(f"  [X] Failed to post for {payload['agent_id']}: {e}")
        return False


def main():
    print("======================================================")
    print("  Populating DPI-LS Main Dashboard (P, Q, E, G, R)  ")
    print("======================================================")
    print()
    
    success_count = 0
    for rating in MOCK_RATINGS:
        print(f"  -> Ingesting run for agent: {rating['agent_id']} ...", end="", flush=True)
        if post_rating(rating):
            print(" [OK]")
            success_count += 1
        time.sleep(0.5)
        
    print()
    if success_count == len(MOCK_RATINGS):
        print("  [V] Successfully populated dashboard with agent data!")
        print("  [V] Open: http://localhost:8000/widget/index.html")
    else:
        print("  [X] Some ingestions failed. Is the backend running on port 8000?")
    print()

if __name__ == "__main__":
    main()
