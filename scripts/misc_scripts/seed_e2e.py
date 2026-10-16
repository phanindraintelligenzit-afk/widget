
import os
import store.db as _db
from store.models import UserRow
_db.configure('sqlite:///D:/DPI-LS/widget/browser_e2e_36a2b6.db')
_db.init_db()
factory = _db.get_session_factory()
with factory() as session:
    if not session.query(UserRow).filter_by(username='alice').first():
        session.add(UserRow(username='alice', password_hash='pass', role='USER'))
        session.add(UserRow(username='bob', password_hash='pass', role='USER'))
        session.commit()
