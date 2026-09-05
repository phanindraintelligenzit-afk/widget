from sqlalchemy import create_engine, text
engine = create_engine('sqlite:///dpi_ls.db')
conn = engine.connect()
print(conn.execute(text("SELECT id FROM score_history WHERE agent_id='chandra-finops' AND score < 80 ORDER BY id DESC LIMIT 1")).scalar())
