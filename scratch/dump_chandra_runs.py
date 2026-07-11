import sqlite3
import json

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

# Get columns of score_history
cur.execute("PRAGMA table_info(score_history)")
cols = [row[1] for row in cur.fetchall()]
print("score_history columns:", cols)

print("=== score_history table ===")
# Build query dynamically based on actual columns
select_cols = ", ".join(cols)
cur.execute(f"SELECT {select_cols} FROM score_history WHERE agent_id='chandra-finops' ORDER BY id DESC LIMIT 5")
for row in cur.fetchall():
    data = dict(zip(cols, row))
    print(f"ID: {data.get('id')} | Agent: {data.get('agent_id')} | Score: {data.get('score')} | Raw Score: {data.get('raw_score')} | Created: {data.get('created_at')}")
    for k in ['metrics', 'breakdown', 'details']:
        if k in data and data[k]:
            try:
                parsed = json.loads(data[k])
                print(f"{k.capitalize()}:", json.dumps(parsed, indent=2))
            except Exception:
                print(f"{k.capitalize()}:", data[k])
    print("-" * 50)

conn.close()
