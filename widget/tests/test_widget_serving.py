"""The widget is the demo surface — make sure it actually ships from the API."""
from __future__ import annotations


def test_widget_js_served(client):
    r = client.get("/widget/dpi-ls.js")
    assert r.status_code == 200
    body = r.text
    # The component definitions and one-tag drop-in contract must be intact.
    assert "customElements.define(\"dpi-ls-board\"" in body
    assert "customElements.define(\"dpi-ls-agent\"" in body
    # Both endpoints the widget polls.
    assert "/ratings" in body
    assert "/agents/" in body


def test_widget_demo_html_served(client):
    r = client.get("/widget/demo.html")
    assert r.status_code == 200
    assert "<dpi-ls-board" in r.text
    assert "<dpi-ls-agent" in r.text
    assert "/widget/dpi-ls.js" in r.text


def test_root_redirects_to_demo(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/widget/demo.html")


def test_cors_headers_on_ratings(client):
    r = client.get("/ratings", headers={"Origin": "https://embed.example.com"})
    assert r.status_code == 200
    # Allow-Origin echoed (default config is *).
    assert r.headers.get("access-control-allow-origin") in ("*", "https://embed.example.com")
