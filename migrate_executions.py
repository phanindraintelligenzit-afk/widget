import sqlite3

conn = sqlite3.connect("dpi_ls.db")
cur = conn.cursor()

new_cols = [
    ("queued_at", "REAL"),
    ("started_at", "REAL"),
    ("completed_at", "REAL"),
    ("timeout_seconds", "INTEGER DEFAULT 300"),
    ("result", "TEXT"),
    ("cancelled_by", "TEXT"),
    ("worker_pid", "INTEGER"),
    ("retry_count", "INTEGER DEFAULT 0"),
]

cur.execute("PRAGMA table_info(executions)")
existing = {r[1] for r in cur.fetchall()}
print("existing:", existing)

for col, coltype in new_cols:
    if col not in existing:
        cur.execute(f"ALTER TABLE executions ADD COLUMN {col} {coltype}")
        print(f"  added: {col}")
    else:
        print(f"  skip (exists): {col}")

cur.execute("UPDATE executions SET status='SUCCESS' WHERE status='completed'")
cur.execute("UPDATE executions SET status='FAILED' WHERE status='failed'")
cur.execute("UPDATE executions SET status='RUNNING' WHERE status='running'")
cur.execute("UPDATE executions SET status='QUEUED' WHERE status='pending'")

conn.commit()
conn.close()
print("Migration done")
