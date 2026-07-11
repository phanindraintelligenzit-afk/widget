def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_adapters_lists_webhook_acme(client):
    r = client.get("/adapters")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert "webhook:acme" in names  # auto-registered from fixtures/mapping_acme.yaml
