import sqlite3, json

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

print("=== Q sub-scores (Accuracy, Consistency, Hallucination) — latest per agent ===")
print(f"{'Agent':<35} {'Q Score':>8} {'Accuracy':>10} {'Consistency':>13} {'Hallucination':>15}  {'Source'}")
print("-" * 100)

cur.execute("""
    SELECT o.agent_id, a.name, o.payload,
           s.metrics, s.score
    FROM observations o
    JOIN agents a ON a.id = o.agent_id
    JOIN score_history s ON s.observation_id = o.id
    WHERE s.id IN (
        SELECT MAX(id) FROM score_history GROUP BY agent_id
    )
    ORDER BY a.name
""")

rows = cur.fetchall()
if not rows:
    # Try without the join constraint
    cur.execute("""
        SELECT o.agent_id, a.name, o.payload
        FROM observations o
        JOIN agents a ON a.id = o.agent_id
        WHERE o.id IN (
            SELECT MAX(id) FROM observations GROUP BY agent_id
        )
        ORDER BY a.name
    """)
    rows2 = cur.fetchall()
    print(f"(No score join; showing from observations directly, {len(rows2)} rows)")
    for agent_id, name, payload_raw in rows2:
        payload = json.loads(payload_raw) if payload_raw else {}
        quality = payload.get("quality")
        if quality:
            acc  = quality.get("accuracy",          "—")
            cons = quality.get("consistency",        "—")
            hall = quality.get("hallucination_rate", "—")
            print(f"  {name}: acc={acc} cons={cons} hall={hall}")
        else:
            print(f"  {name}: no quality field in payload")
else:
    for agent_id, name, payload_raw, metrics_raw, score in rows:
        payload = json.loads(payload_raw) if payload_raw else {}
        metrics = json.loads(metrics_raw) if metrics_raw else {}
        quality = payload.get("quality")
        q_composite = metrics.get("Q", None)
        q_str = f"{round(q_composite*100):3d}" if isinstance(q_composite, float) else " — "

        if quality:
            acc  = quality.get("accuracy",          None)
            cons = quality.get("consistency",        None)
            hall = quality.get("hallucination_rate", None)
            source = quality.get("source", "llm")
            acc_s  = f"{acc*100:6.1f}%" if isinstance(acc,  float) else "  N/A  "
            cons_s = f"{cons*100:6.1f}%" if isinstance(cons, float) else "  N/A  "
            hall_s = f"{hall*100:6.1f}%" if isinstance(hall, float) else "  N/A  "
        else:
            acc_s = cons_s = hall_s = "  N/A  "
            source = "none"

        print(f"{name:<35} {q_str:>8} {acc_s:>10} {cons_s:>13} {hall_s:>15}  {source}")

conn.close()