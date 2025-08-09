"""Tests."""

from __future__ import annotations

import math

import pytest

from hahomematic.model.calculated.support import calculate_apparent_temperature, calculate_dew_point


@pytest.mark.parametrize(
    ("temperature", "humidity", "wind_speed", "expected"),
    [
        # Wind speed at boundary 4.8 should NOT apply wind chill; returns ambient temp rounded
        (10.0, 50, 4.8, 10.0),
        # Below threshold wind with low temp should also return ambient temp
        (5.0, 50, 4.0, 5.0),
    ],
)
def test_apparent_temperature_wind_chill_boundary(temperature, humidity, wind_speed, expected) -> None:
    """Test apparent temperature wind chill boundary."""
    assert calculate_apparent_temperature(temperature, humidity, wind_speed) == expected


def test_apparent_temperature_heat_index_boundary() -> None:
    """Test apparent temperature heat index boundary."""
    # Exactly at 26.7C must trigger heat index calculation
    at = calculate_apparent_temperature(26.7, 60, 0.0)
    assert at is not None
    # Should be greater or equal to the ambient temperature due to humidity
    assert at >= 26.7


def test_dew_point_mid_range_precision() -> None:
    """Test dew point mid-range precision."""
    # Verify dew point is a finite float with typical conditions
    dp = calculate_dew_point(22.0, 55)
    assert isinstance(dp, float)
    assert math.isfinite(dp)
    assert 8.0 <= dp <= 16.0
