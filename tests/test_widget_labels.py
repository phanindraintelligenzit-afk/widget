"""Widget exposes the right human labels.

R is Risk (severity-weighted incidents) per the engine + spec, not
'Reliability'. The widget label table is the only place the user sees
the long form; if it ever drifts, fix here.
"""
from __future__ import annotations


def test_metric_labels_use_risk_not_reliability(client):
    body = client.get("/widget/dpi-ls.js").text
    assert 'R: "Risk' in body
    assert 'Reliability' not in body
    assert 'reliability' not in body


def test_widget_renders_coverage_badge(client):
    body = client.get("/widget/dpi-ls.js").text
    # The new coverage badge code is present.
    assert "coverageBadge" in body
    assert "measured " in body


def test_widget_renders_governance_violation_list(client):
    """The G panel must show the official formula and the
    Action → Incident breakdown, not just the score.
    """
    body = client.get("/widget/dpi-ls.js").text
    # Official DPI-LS governance formula, rendered on the dashboard.
    assert "Governance = 1" in body and "(Total Actions / Policy Violations)" in body
    # The incident rows render "Action Name → Incident Name".
    assert "action_name" in body
    assert "rarr;" in body
    # The panel is gated on the G key.
    assert 'key === "G"' in body
    # The new telemetry fields drive the calculation.
    assert '"Total Actions"' in body
    assert '"Policy Violations"' in body
