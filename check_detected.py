import sqlite3
conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()
c.execute("SELECT metric, detected FROM productivity_resource_evaluations WHERE resource_name = 'Apache SkyWalking'")
rows = c.fetchall()
for row in rows:
    print(row)
