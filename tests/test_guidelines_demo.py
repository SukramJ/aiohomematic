"""Tests."""

from __future__ import annotations

from hahomematic.model.calculated.support import calculate_dew_point


def test_calculate_dew_point_zero_zero_returns_zero_point_zero() -> None:
    """Test calculating frost point."""
    # Edge case handled in implementation: temperature == 0.0 and humidity == 0 returns 0.0
    assert calculate_dew_point(0.0, 0) == 0.0
