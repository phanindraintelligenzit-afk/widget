import sqlite3

conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(c.fetchall())

conn.close()
