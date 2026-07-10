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
    """The G panel must show the operator which rules fired, not just
    the score. The expanded panel groups violations by rule name and
    shows the count + most recent timestamp.
    """
    body = client.get("/widget/dpi-ls.js").text
    # The widget's G panel walks ``sub_metrics.G.violations`` and groups
    # by rule name. The widget code itself is rule-agnostic — rule
    # names come from the API response. The presence of the
    # grouping/render code is what we pin here.
    assert "byAction" in body
    assert "violation rate" in body
    # The panel must be gated on the G key and on the array of
    # violation objects the API emits.
    assert 'key === "G"' in body
    assert "sub.violations" in body
