"""M6 widget surface — new custom elements wired and demo updated."""
from __future__ import annotations


def test_widget_js_defines_m6_components(client):
    body = client.get("/widget/dpi-ls.js").text
    assert "customElements.define(\"dpi-ls-sme-prompt\"" in body
    assert "customElements.define(\"dpi-ls-settings\"" in body
    # Both new components hit their dedicated endpoints.
    assert "/sme-flow/start" in body
    assert "/sme-flow/" in body and "/respond" in body
    assert "/settings" in body


def test_demo_html_embeds_m6_components(client):
    body = client.get("/widget/demo.html").text
    assert "<dpi-ls-sme-prompt" in body
    assert "<dpi-ls-settings" in body
