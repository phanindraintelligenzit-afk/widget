import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

if 'quality_resource_evaluations' in tables:
    cursor.execute("DELETE FROM quality_resource_evaluations WHERE resource_name IN ('LangSmith', 'Confident AI')")
    print(f"Deleted {cursor.rowcount} rows from quality_resource_evaluations")

if 'quality_resource_registry' in tables:
    cursor.execute("DELETE FROM quality_resource_registry WHERE name IN ('LangSmith', 'Confident AI')")
    print(f"Deleted {cursor.rowcount} rows from quality_resource_registry")

conn.commit()
conn.close()
