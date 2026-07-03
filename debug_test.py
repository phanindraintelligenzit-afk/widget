import json
from pathlib import Path
import os
import time

# Set env vars before anything else
os.environ["MAPPINGS_DIR"] = str(Path("fixtures").absolute())

from store import db as db_mod

def setup_db():
    db_mod._engine = None
    db_mod._SessionLocal = None
    db_mod.configure("sqlite:///:memory:")
    db_mod.init_db()

    from ingestion import clear
    from ingestion.sources import clear as clear_sources
    clear()
    clear_sources()

def post_canonical(client, fixture_name: str):
    p = Path("fixtures") / f"obs_{fixture_name}.json"
    obs = json.loads(p.read_text())
    obs.pop("_label", None)
    t0 = time.time()
    r = client.post("/ingest", json=obs)
    t1 = time.time()
    print(f"POST /ingest status {r.status_code} in {t1-t0:.3f}s")
    assert r.status_code == 200, r.text
    return r.json()

def main():
    setup_db()
    
    from api.app import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        print("Test client created.")
        post_canonical(client, "strong")
        post_canonical(client, "strong")
        post_canonical(client, "strong")
        
        r = client.get("/agents/agent-strong-001/history")
        h = r.json()
        print(f"History length: {len(h)}")
        for x in h:
            print(x["computed_at"])

if __name__ == "__main__":
    main()
