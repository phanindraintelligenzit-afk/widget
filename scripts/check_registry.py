import sqlite3
conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()
c.execute("SELECT name, integration_implemented FROM productivity_resource_registry")
print(c.fetchall())
