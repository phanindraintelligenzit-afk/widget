import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

if 'enterprise_productivity_evaluations' in tables:
    cursor.execute("DELETE FROM enterprise_productivity_evaluations WHERE resource_name = 'Prometheus'")
    print(f"Deleted {cursor.rowcount} rows from enterprise_productivity_evaluations")

if 'enterprise_productivity_registry' in tables:
    cursor.execute("DELETE FROM enterprise_productivity_registry WHERE name = 'Prometheus'")
    print(f"Deleted {cursor.rowcount} rows from enterprise_productivity_registry")

if 'risk_resource_evaluations' in tables:
    cursor.execute("DELETE FROM risk_resource_evaluations WHERE resource_name = 'Prometheus'")
    print(f"Deleted {cursor.rowcount} rows from risk_resource_evaluations")

if 'risk_resource_registry' in tables:
    cursor.execute("DELETE FROM risk_resource_registry WHERE name = 'Prometheus'")
    print(f"Deleted {cursor.rowcount} rows from risk_resource_registry")

conn.commit()
conn.close()
