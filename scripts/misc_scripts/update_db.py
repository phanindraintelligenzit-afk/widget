import sqlite3

conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()

# Check settings table
c.execute("UPDATE configurations SET configuration_value = '200.0' WHERE configuration_key = 'human_cost_per_output'")
print(f"Updated {c.rowcount} rows in configurations")

conn.commit()
conn.close()
