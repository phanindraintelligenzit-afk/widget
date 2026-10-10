import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()

# Check tables just to be sure
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

if 'governance_incidents' in tables:
    cursor.execute("DELETE FROM governance_incidents WHERE source_resource = 'Microsoft Presidio'")
    print(f"Deleted {cursor.rowcount} rows from governance_incidents")

if 'governance_resource_evaluations' in tables:
    cursor.execute("DELETE FROM governance_resource_evaluations WHERE resource_name = 'Microsoft Presidio'")
    print(f"Deleted {cursor.rowcount} rows from governance_resource_evaluations")

if 'governance_resource_registry' in tables:
    cursor.execute("DELETE FROM governance_resource_registry WHERE name = 'Microsoft Presidio'")
    print(f"Deleted {cursor.rowcount} rows from governance_resource_registry")

conn.commit()
conn.close()
