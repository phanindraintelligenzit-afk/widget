import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()

# Check tables just to be sure
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

if 'risk_incidents' in tables:
    cursor.execute("DELETE FROM risk_incidents WHERE source_resource IN ('Rebuff', 'TruLens', 'LLMGuard')")
    print(f"Deleted {cursor.rowcount} rows from risk_incidents")

if 'risk_resource_evaluations' in tables:
    cursor.execute("DELETE FROM risk_resource_evaluations WHERE resource_name IN ('Rebuff', 'TruLens', 'LLMGuard')")
    print(f"Deleted {cursor.rowcount} rows from risk_resource_evaluations")

if 'risk_resource_registry' in tables:
    cursor.execute("DELETE FROM risk_resource_registry WHERE name IN ('Rebuff', 'TruLens', 'LLMGuard')")
    print(f"Deleted {cursor.rowcount} rows from risk_resource_registry")

conn.commit()
conn.close()
