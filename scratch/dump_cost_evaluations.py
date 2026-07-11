import sqlite3

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

# Get columns of cost_resource_evaluations
cur.execute("PRAGMA table_info(cost_resource_evaluations)")
cols = [row[1] for row in cur.fetchall()]
print("cost_resource_evaluations columns:", cols)

print("=== cost_resource_evaluations (Langfuse & Arize Phoenix only) ===")
cur.execute("""
    SELECT id, resource_name, metric, detected, current_value, status, evidence
    FROM cost_resource_evaluations
    WHERE resource_name IN ('Langfuse', 'Arize Phoenix')
    ORDER BY resource_name, metric
""")
for row in cur.fetchall():
    print(f"ID: {row[0]} | Resource: {row[1]} | Metric: {row[2]} | Detected: {row[3]} | Value: {row[4]} | Status: {row[5]}")
    print(f"  Evidence: {row[6]}")
    print("-" * 50)

conn.close()
