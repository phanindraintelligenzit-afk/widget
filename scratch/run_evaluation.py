"""
Simple evaluation runner - no litellm, no internet needed.
Just calls the local DPI-LS API to run evaluations and shows results.
"""
import urllib.request
import json
import sys
import time

BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None) -> dict:
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    print("=" * 60)
    print("  DPI-LS Evaluation Runner  (no litellm / internet needed)")
    print("=" * 60)
    print()

    # Step 1 — Run full evaluation
    print("  [1/3] Running full technical evaluation …")
    try:
        results = call("POST", "/api/cost-evaluation/evaluate")
        print(f"  [V]  Evaluation complete: {len(results)} metric rows saved")
    except Exception as e:
        print(f"  [X]  Evaluation failed: {e}")
        print("     Make sure the backend is running:  uv run uvicorn api.app:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    # Step 2 — Auto-verify dashboard for each active resource
    print()
    ACTIVE = ["Langfuse", "Prometheus", "Grafana", "OpenTelemetry", "Arize Phoenix", "MLflow"]
    print(f"  [2/3] Auto-verifying dashboards for {len(ACTIVE)} resources …")
    for res in ACTIVE:
        try:
            call("POST", "/api/cost-evaluation/verify-dashboard",
                 {"resource_name": res, "metric": None})
            print(f"       [V]  {res}")
        except Exception as e:
            print(f"       [X]  {res}: {e}")
    time.sleep(0.5)

    # Step 3 — Fetch and summarise results
    print()
    print("  [3/3] Fetching final results …")
    try:
        rows = call("GET", "/api/cost-evaluation/results")
    except Exception as e:
        print(f"  [X]  Could not fetch results: {e}")
        sys.exit(1)

    GROUPS = {
        "C": ["model_cost", "token_cost", "prompt_cost", "completion_cost",
              "AI_cost_per_output", "Human_cost_per_output", "utilization", "total_cost_of_ownership"],
        "V": ["validated_components", "required_components", "validation_score"],
        "Q": ["hallucination_score", "relevance_score", "groundedness_score",
              "user_feedback_score", "model_correctness"],
    }
    GROUP_COLOR = {"C": "💰 Cost (C)", "V": "✅ Validation (V)", "Q": "🧬 Quality (Q)"}

    active_rows = [r for r in rows if r.get("resource_name") in ACTIVE]

    # Group by resource
    by_res: dict[str, list] = {}
    for r in active_rows:
        by_res.setdefault(r["resource_name"], []).append(r)

    total_detected = sum(1 for r in active_rows if r.get("detected"))
    total = len(active_rows)
    print()
    print(f"  {'─'*56}")
    print(f"  SUMMARY  |  {total_detected}/{total} metrics detected")
    print(f"  {'─'*56}")
    for res in ACTIVE:
        metrics = by_res.get(res, [])
        det = sum(1 for m in metrics if m.get("detected"))
        print(f"\n  {res} ({det}/{len(metrics)})")
        for grp_key, grp_metrics in GROUPS.items():
            grp_rows = [m for m in metrics if m["metric"] in grp_metrics]
            if not grp_rows:
                continue
            print(f"    {GROUP_COLOR[grp_key]}")
            for m in grp_rows:
                icon = "[V]" if m.get("detected") else "[X]"
                val = m.get("current_value", "0.0")
                print(f"      {m['metric']:<30} {val:<12} {icon}")

    print()
    print("  [V] Done! Open http://localhost:8000/widget/resources.html to see the full UI.")
    print()


if __name__ == "__main__":
    main()
