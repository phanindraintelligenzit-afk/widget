import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

if 'execution_incidents' in tables:
    cursor.execute("DELETE FROM execution_incidents WHERE source_resource IN ('Phoenix', 'Traceloop')")
    print(f"Deleted {cursor.rowcount} rows from execution_incidents")

if 'execution_resource_evaluations' in tables:
    cursor.execute("DELETE FROM execution_resource_evaluations WHERE resource_name IN ('Phoenix', 'Traceloop')")
    print(f"Deleted {cursor.rowcount} rows from execution_resource_evaluations")

if 'execution_resource_registry' in tables:
    cursor.execute("DELETE FROM execution_resource_registry WHERE name IN ('Phoenix', 'Traceloop')")
    print(f"Deleted {cursor.rowcount} rows from execution_resource_registry")

conn.commit()
conn.close()
