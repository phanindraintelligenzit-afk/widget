"""Tests for the DPI-LS Productivity Feed (P) calculations and API settings integration."""
from __future__ import annotations

import pytest

from contract import AgentBaseline, AgentObservation, Settings, TaskStats
from engine.metrics import compute_P, metrics_from_observation, metrics_from_partial
from fixtures import load


def test_compute_p_normalization_factor():
    """Verify compute_P applies normalization factor correctly and clamps to [0,1]."""
    # Default factor = 1.0
    assert compute_P(10, 100, 1.0) == 0.1
    assert compute_P(100, 100, 1.0) == 1.0
    assert compute_P(150, 100, 1.0) == 1.0

    # Custom factor (e.g. old 0.27)
    assert compute_P(10, 100, 0.27) == pytest.approx(0.027)
    assert compute_P(100, 100, 0.27) == pytest.approx(0.27)
    assert compute_P(400, 100, 0.27) == 1.0  # capped at 1.0

    # Scale factor > 1.0
    assert compute_P(10, 100, 2.0) == 0.2
    assert compute_P(50, 100, 2.0) == 1.0  # capped at 1.0

    # Edge cases
    assert compute_P(0, 100, 1.5) == 0.0
    assert compute_P(10, 0, 1.5) == 0.0
    assert compute_P(-10, 100, 1.5) == 0.0


def test_metrics_from_observation_applies_normalization():
    """Verify metrics_from_observation passes Settings.normalization_factor to compute_P."""
    sample_observation = load("strong")
    # Ensure tasks are completed so P has a numerator
    sample_observation.tasks = TaskStats(assigned=10, completed=5, failed=0)
    baseline = AgentBaseline(agent_id=sample_observation.agent_id, human_output_per_period=10.0)

    # 1. Default settings: factor = 1.0
    # P = min(1.0, (5 / 10) * 1.0) = 0.5
    settings_default = Settings()
    assert settings_default.normalization_factor == 1.0
    metrics_default = metrics_from_observation(sample_observation, settings_default, baseline)
    assert metrics_default["P"] == 0.5

    # 2. Custom settings: factor = 1.5
    # P = min(1.0, (5 / 10) * 1.5) = 0.75
    settings_custom = Settings(normalization_factor=1.5)
    metrics_custom = metrics_from_observation(sample_observation, settings_custom, baseline)
    assert metrics_custom["P"] == 0.75

    # 3. Custom settings: factor = 0.27
    # P = min(1.0, (5 / 10) * 0.27) = 0.135
    settings_old = Settings(normalization_factor=0.27)
    metrics_old = metrics_from_observation(sample_observation, settings_old, baseline)
    assert metrics_old["P"] == pytest.approx(0.135)


def test_api_settings_normalization_factor(client):
    """Verify that settings can be retrieved and updated via API, maintaining the default."""
    # Get current settings
    response = client.get("/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["normalization_factor"] == 1.0

    # Update settings with custom normalization_factor
    data["normalization_factor"] = 0.5
    put_response = client.put("/settings", json=data)
    assert put_response.status_code == 200
    updated_data = put_response.json()
    assert updated_data["normalization_factor"] == 0.5

    # Get settings again to confirm persistence
    get_response = client.get("/settings")
    assert get_response.status_code == 200
    assert get_response.json()["normalization_factor"] == 0.5

    # Clean up / reset to default
    data["normalization_factor"] = 1.0
    client.put("/settings", json=data)
