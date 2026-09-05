import sqlite3

conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()

c.execute("SELECT * FROM agent_configuration")
print(c.fetchall())

conn.close()
