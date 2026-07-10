import sqlite3

conn = sqlite3.connect('dpi_ls.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables:")
for table in tables:
    table_name = table[0]
    print(f"- {table_name}")
    
    # Get schema for table
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    print("  Columns:", [col[1] for col in columns])
    print()

conn.close()
