"""Tests."""

from __future__ import annotations

import math

import pytest

from aiohomematic.model.calculated.support import (
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_frost_point,
    calculate_operating_voltage_level,
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


def test_calculate_dew_point_zero_zero_returns_zero_point_zero() -> None:
    """Test calculating frost point."""
    # Edge case handled in implementation: temperature == 0.0 and humidity == 0 returns 0.0
    assert calculate_dew_point(0.0, 0) == 0.0


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


@pytest.mark.parametrize(
    ("operating_voltage", "low_bat_limit", "voltage_max"),
    [
        (None, 2.0, 3.0),
        (2.5, None, 3.0),
        (2.5, 2.0, None),
    ],
)
def test_calculate_operating_voltage_level_none_inputs(operating_voltage, low_bat_limit, voltage_max) -> None:
    """If any input is None, the result should be None."""
    assert calculate_operating_voltage_level(operating_voltage, low_bat_limit, voltage_max) is None


def test_calculate_operating_voltage_level_normal() -> None:
    """Typical calculation with rounding to one decimal."""
    # ((2.5 - 2.0) / (3.0 - 2.0)) * 100 = 50.0
    assert calculate_operating_voltage_level(2.5, 2.0, 3.0) == 50.0

    """Validate rounding to one decimal place."""
    # ((2.26 - 2.0) / 1.0) * 100 = 26.0 -> 26.0
    assert calculate_operating_voltage_level(2.26, 2.0, 3.0) == 26.0
    # ((2.255 - 2.0) / 1.0) * 100 = 25.5 -> 25.5 exact boundary
    assert calculate_operating_voltage_level(2.255, 2.0, 3.0) == 25.5

    """Values below or equal to low_bat_limit clamp to 0."""
    assert calculate_operating_voltage_level(1.9, 2.0, 3.0) == 0.0
    assert calculate_operating_voltage_level(2.0, 2.0, 3.0) == 0.0

    """Values above or equal to voltage_max clamp to 100."""
    assert calculate_operating_voltage_level(3.5, 2.0, 3.0) == 100.0
    assert calculate_operating_voltage_level(3.0, 2.0, 3.0) == 100.0
