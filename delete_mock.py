import sqlite3
conn = sqlite3.connect('dpi_ls.db')
conn.execute("DELETE FROM governance_incidents WHERE incident_id IN ('gov_mock_1', 'gov_mock_2')")
conn.commit()
print('Mock incidents deleted')
