from store.db import get_engine, configure
from sqlalchemy import text
configure("sqlite:///store/dpi_ls.db")
engine = get_engine()
with engine.begin() as conn:
    conn.execute(text("DELETE FROM validation_resource_evaluations WHERE current_value = 'Unavailable' OR metric LIKE '%_evidence'"))
