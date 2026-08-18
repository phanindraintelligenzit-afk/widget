import sqlite3
c = sqlite3.connect('dpi_ls.db')
cur = c.cursor()
cur.execute("SELECT score, raw_score FROM score_history WHERE agent_id='chandra-finops' ORDER BY id DESC LIMIT 1")
print(cur.fetchone())
