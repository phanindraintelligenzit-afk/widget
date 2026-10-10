import sys

def patch_db():
    with open('store/db.py', 'r', encoding='utf-8') as f:
        content = f.read()

    t1 = """    if is_memory:
        # Share the same in-memory DB across sessions for the duration
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool

    _engine = create_engine(url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine"""

    r1 = """    if is_memory:
        # Share the same in-memory DB across sessions for the duration
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool
    elif is_sqlite:
        kwargs["pool_size"] = 20
        kwargs["max_overflow"] = 40
        kwargs["pool_timeout"] = 60.0

    _engine = create_engine(url, **kwargs)
    
    if is_sqlite:
        from sqlalchemy import event
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine"""

    if t1 not in content:
        print("Could not find target block in db.py")
        sys.exit(1)

    content = content.replace(t1, r1)

    with open('store/db.py', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully patched db.py")

if __name__ == '__main__':
    patch_db()
