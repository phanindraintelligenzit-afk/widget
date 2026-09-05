import sqlite3
import json

conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()

c.execute("SELECT payload FROM settings WHERE id = 1")
payload = json.loads(c.fetchone()[0])
print(payload)

payload['human_cost_per_output'] = 200.0

c.execute("UPDATE settings SET payload = ? WHERE id = 1", (json.dumps(payload),))
conn.commit()

print("Updated human_cost_per_output to 200.0")

conn.close()
