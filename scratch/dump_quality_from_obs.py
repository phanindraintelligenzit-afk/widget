import sqlite3
import json

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

cur.execute("""
    SELECT id, payload, received_at 
    FROM observations 
    WHERE agent_id='chandra-finops'
    ORDER BY id DESC LIMIT 5
""")

print("=== Observations Quality and Cost Data ===")
for row in cur.fetchall():
    obs_id = row[0]
    payload = json.loads(row[1]) if row[1] else {}
    received = row[2]
    
    quality = payload.get("quality") or {}
    cost = payload.get("cost") or {}
    val = payload.get("validation") or {}
    
    print(f"Obs ID: {obs_id} | Ingested: {received}")
    print(f"  Quality: {quality}")
    print(f"  Cost: {cost}")
    print(f"  Validation: {val}")
    print("-" * 50)

conn.close()
