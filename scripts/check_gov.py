import sqlite3
conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()
c.execute("SELECT metric, current_value FROM governance_resource_evaluations WHERE resource_name = 'Open Policy Agent'")
rows = c.fetchall()
for row in rows:
    print(row)
