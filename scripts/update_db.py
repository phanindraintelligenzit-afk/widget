import sqlite3
conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()
c.execute("UPDATE productivity_resource_registry SET integration_implemented = 1 WHERE name = 'Apache SkyWalking'")
c.execute("UPDATE productivity_resource_evaluations SET status = 'SUCCESS' WHERE resource_name = 'Apache SkyWalking'")
conn.commit()
print('Updated')
