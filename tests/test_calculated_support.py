"""Tests."""

from __future__ import annotations

import math

from hahomematic.model.calculated.support import (
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_frost_point,
    calculate_vapor_concentration,
)


def test_calculate_vapor_concentration_basic() -> None:
    """Test calculating vapor concentration."""
    # 0% humidity should yield 0.0 regardless of temperature
    assert calculate_vapor_concentration(0.0, 0) == 0.0
    # Typical indoor conditions should be a positive, reasonable value
    vc = calculate_vapor_concentration(25.0, 50)
    assert vc is not None
    assert isinstance(vc, float)
    # Rough sanity bounds (absolute humidity at 25C/50% is ~10-13 g/m³)
    assert 8.0 <= vc <= 15.0


def test_calculate_dew_point_basic_and_zero_edge() -> None:
    """Test calculating dew point."""
    # Realistic mid-range input: dew point should be around 8-12C
    dp = calculate_dew_point(20.0, 50)
    assert dp is not None
    assert 5.0 <= dp <= 15.0
    # Special error-handling branch returns 0.0 for (0,0)
    # This path occurs via math domain error during log(0), caught by except
    dp_zero = calculate_dew_point(0.0, 0)
    assert dp_zero == 0.0


def test_calculate_dew_point_invalid_humidity() -> None:
    """Test calculating dew point."""
    # Negative humidity triggers ValueError in log due to negative vp
    dp = calculate_dew_point(20.0, -10)
    assert dp is None


def test_calculate_apparent_temperature_wind_chill_heat_index_and_normal() -> None:
    """Test calculating apparent temperature wind chill heat and normal."""
    # Wind chill case (temp <= 10 and wind_speed > 4.8) -> less than ambient
    at_wind = calculate_apparent_temperature(5.0, 50, 10.0)
    assert at_wind is not None
    assert at_wind < 5.0

    # Heat index case (temp >= 26.7) -> greater than ambient in humid conditions
    at_heat = calculate_apparent_temperature(30.0, 70, 2.0)
    assert at_heat is not None
    assert at_heat > 30.0

    # Normal case -> equals temperature (rounded)
    at_norm = calculate_apparent_temperature(20.0, 50, 1.0)
    assert at_norm == 20.0


def test_calculate_apparent_temperature_zero_edge() -> None:
    """Test calculating apparent temperature edge."""
    # For 0C and 0% humidity with low wind, function should return 0.0 (no exception branch needed here)
    assert calculate_apparent_temperature(0.0, 0, 1.0) == 0.0


def test_calculate_frost_point_normal_and_none_branch() -> None:
    """Test calculating frost point."""
    # Normal humid cold air -> frost point should be <= temperature and usually <= 0
    fp = calculate_frost_point(0.0, 80)
    assert fp is not None
    assert fp <= 0.0
    assert fp <= 0.0 <= 0.1  # ensure it's not a positive number

    # If dew point cannot be computed -> frost point None
    fp_none = calculate_frost_point(20.0, -10)
    assert fp_none is None


def test_calculate_frost_point_zero_zero() -> None:
    """Test calculating frost point."""
    # For (0,0), dew point returns 0.0 and frost point can be computed without error
    fp = calculate_frost_point(0.0, 0)
    assert fp is not None
    # Should be a finite float
    assert isinstance(fp, float)
    assert math.isfinite(fp)
