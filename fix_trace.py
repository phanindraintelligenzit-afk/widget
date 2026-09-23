with open('tests/test_traceability.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''def test_missing_trace_returns_404():
    from fastapi.testclient import TestClient
    from api.app import app
    import jwt
    from datetime import datetime, timedelta, timezone
    client = TestClient(app)
    token = jwt.encode(
        {"sub": "alice", "role": "USER", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "SUPER_SECRET_JWT_KEY_FOR_DPI_LS",
        algorithm="HS256"
    )
    response = client.get("/trace/fake-run-id", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404'''

content = content.replace('''def test_missing_trace_returns_404():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    response = client.get("/trace/fake-run-id")
    assert response.status_code == 404''', replacement)

with open('tests/test_traceability.py', 'w', encoding='utf-8') as f:
    f.write(content)
