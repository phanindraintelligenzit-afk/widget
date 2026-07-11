import sqlite3
conn = sqlite3.connect('dpi_ls.db')
c = conn.cursor()
c.execute("DELETE FROM validation_resource_evaluations WHERE resource_name = 'DeepEval'")
conn.commit()
print('Deleted DeepEval rows:', c.rowcount)
c.execute("SELECT COUNT(*) FROM validation_resource_evaluations WHERE resource_name = 'DeepEval'")
print('Remaining DeepEval rows:', c.fetchone()[0])
