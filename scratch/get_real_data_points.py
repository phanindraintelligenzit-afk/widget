import sqlite3
import json

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

# Get partial observations for langfuse and arize
cur.execute("""
    SELECT id, source, payload, received_at 
    FROM partial_observations 
    WHERE agent_id='chandra-finops' AND source IN ('langfuse', 'arize')
    ORDER BY id DESC
""")

print("=== Captured Telemetry Runs in partial_observations ===")
rows = cur.fetchall()
print(f"Total rows found: {len(rows)}")
for row in rows:
    obs_id = row[0]
    source = row[1]
    payload = json.loads(row[2]) if row[2] else {}
    received = row[3]
    
    print(f"Observation ID: {obs_id} | Source: {source} | Ingested: {received}")
    
    # Cost
    cost = payload.get("cost") or {}
    in_tokens = cost.get("input_tokens", 0)
    out_tokens = cost.get("output_tokens", 0)
    total_tokens = in_tokens + out_tokens
    model_cost = cost.get("model_cost", 0.0)
    human_cost = cost.get("Human_cost", 0.0)
    tco = model_cost + human_cost
    
    # Latency / attempts
    execs = payload.get("executions") or {}
    attempts = execs.get("attempts", 1)
    successful = execs.get("successful", 1)
    
    # Validation
    val = payload.get("validation") or {}
    req_comp = val.get("required_components", 0)
    val_comp = val.get("validated_components", 0)
    val_score = val_comp / max(req_comp, 1) if req_comp > 0 else 1.0
    
    # Quality (Phoenix metrics)
    quality = payload.get("quality") or {}
    acc = quality.get("accuracy")
    consistency = quality.get("consistency")
    hallucination = quality.get("hallucination_rate")
    
    print(f"  Tokens: Input={in_tokens}, Output={out_tokens}, Total={total_tokens}")
    print(f"  Cost: Model=${model_cost:.2f}, Human=${human_cost:.2f}, TCO=${tco:.2f}")
    print(f"  Validation: Req={req_comp}, Val={val_comp}, Score={val_score:.2f}")
    if quality:
        print(f"  Quality: Accuracy={acc}, Consistency={consistency}, Hallucination={hallucination}")
    print("-" * 50)

conn.close()
