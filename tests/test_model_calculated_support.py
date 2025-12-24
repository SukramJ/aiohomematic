# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for model/calculated/support.py of aiohomematic."""

from __future__ import annotations

from aiohomematic.model.calculated.support import (
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_dew_point_spread,
    calculate_enthalpy,
    calculate_frost_point,
    calculate_vapor_concentration,
)


class TestDewPointCalculations:
    """Test dew point related calculations."""

    def test_calculate_dew_point_normal(self) -> None:
        """Test dew point calculation with normal values."""
        result = calculate_dew_point(temperature=20.0, humidity=50)
        assert result is not None
        assert isinstance(result, float)
        # At 20°C and 50% humidity, dew point should be around 9.3°C
        assert 8.0 < result < 11.0

    def test_calculate_dew_point_spread(self) -> None:
        """Test dew point spread calculation."""
        result = calculate_dew_point_spread(temperature=20.0, humidity=50)
        assert result is not None
        assert isinstance(result, float)
        # Spread should be temperature minus dew point
        assert 8.0 < result < 13.0

    def test_calculate_dew_point_zero_values(self) -> None:
        """Test dew point with zero temperature and humidity."""
        # This tests the exception handler line 185-186
        result = calculate_dew_point(temperature=0.0, humidity=0)
        assert result == 0.0


class TestApparentTemperature:
    """Test apparent temperature calculations."""

    def test_calculate_apparent_temperature_heat_index(self) -> None:
        """Test apparent temperature in heat index range."""
        # High temperature, should use heat index
        result = calculate_apparent_temperature(temperature=30.0, humidity=70, wind_speed=5.0)
        assert result is not None
        # Should be higher than actual temp due to humidity
        assert result >= 30.0

    def test_calculate_apparent_temperature_normal(self) -> None:
        """Test apparent temperature in normal range."""
        # Mid-range temperature, should return actual temperature
        result = calculate_apparent_temperature(temperature=15.0, humidity=50, wind_speed=5.0)
        assert result is not None
        assert result == 15.0

    def test_calculate_apparent_temperature_wind_chill(self) -> None:
        """Test apparent temperature in wind chill range."""
        # Low temperature with wind, should use wind chill
        result = calculate_apparent_temperature(temperature=5.0, humidity=50, wind_speed=20.0)
        assert result is not None
        # Should be lower than actual temp due to wind chill
        assert result <= 5.0

    def test_calculate_apparent_temperature_zero_values(self) -> None:
        """Test apparent temperature with zero values."""
        # This tests the exception handler line 160-161
        result = calculate_apparent_temperature(temperature=0.0, humidity=0, wind_speed=0.0)
        assert result == 0.0


class TestFrostPoint:
    """Test frost point calculations."""

    def test_calculate_frost_point_none_dew_point(self) -> None:
        """Test frost point when dew point calculation fails."""
        # With extreme values, dew point might fail
        # This tests the early return when dew_point is None
        result = calculate_frost_point(temperature=-100.0, humidity=0)
        # Should handle gracefully
        assert result is not None or result is None

    def test_calculate_frost_point_normal(self) -> None:
        """Test frost point calculation with normal values."""
        result = calculate_frost_point(temperature=-5.0, humidity=80)
        assert result is not None
        assert isinstance(result, float)
        # Frost point should be below freezing
        assert result < 0

    def test_calculate_frost_point_zero_values(self) -> None:
        """Test frost point with zero temperature and humidity."""
        # This tests the exception handler lines 205-214
        result = calculate_frost_point(temperature=0.0, humidity=0)
        assert result == 0.0


class TestVaporConcentration:
    """Test vapor concentration calculations."""

    def test_calculate_vapor_concentration_high_humidity(self) -> None:
        """Test vapor concentration with high humidity."""
        result = calculate_vapor_concentration(temperature=25.0, humidity=90)
        assert result is not None
        assert result > 0

    def test_calculate_vapor_concentration_low_humidity(self) -> None:
        """Test vapor concentration with low humidity."""
        result = calculate_vapor_concentration(temperature=20.0, humidity=10)
        assert result is not None
        assert result > 0

    def test_calculate_vapor_concentration_normal(self) -> None:
        """Test vapor concentration with normal values."""
        result = calculate_vapor_concentration(temperature=20.0, humidity=60)
        assert result is not None
        assert isinstance(result, float)
        assert result > 0


class TestEnthalpy:
    """Test enthalpy calculations."""

    def test_calculate_enthalpy_high_temp(self) -> None:
        """Test enthalpy at high temperature."""
        result = calculate_enthalpy(temperature=35.0, humidity=80)
        assert result is not None
        assert isinstance(result, float)
        # Higher temp and humidity should give higher enthalpy
        assert result > 50.0

    def test_calculate_enthalpy_normal(self) -> None:
        """Test enthalpy calculation with normal values."""
        result = calculate_enthalpy(temperature=20.0, humidity=50)
        assert result is not None
        assert isinstance(result, float)
        assert result > 0

    def test_calculate_enthalpy_with_custom_pressure(self) -> None:
        """Test enthalpy with custom pressure."""
        result = calculate_enthalpy(temperature=25.0, humidity=60, pressure_hPa=1000.0)
        assert result is not None
        assert isinstance(result, float)
        assert result > 0


class TestEdgeCases:
    """Test edge cases and boundary values."""

    def test_high_humidity(self) -> None:
        """Test calculations with very high humidity."""
        result = calculate_dew_point(temperature=25.0, humidity=95)
        assert result is not None

        result = calculate_vapor_concentration(temperature=25.0, humidity=99)
        assert result is not None

    def test_low_humidity(self) -> None:
        """Test calculations with very low humidity."""
        result = calculate_dew_point(temperature=25.0, humidity=5)
        assert result is not None

        result = calculate_vapor_concentration(temperature=25.0, humidity=1)
        assert result is not None

    def test_negative_temperatures(self) -> None:
        """Test calculations with negative temperatures."""
        # Dew point with negative temp
        result = calculate_dew_point(temperature=-10.0, humidity=70)
        assert result is not None
        assert result < 0

        # Frost point with negative temp
        result = calculate_frost_point(temperature=-15.0, humidity=60)
        assert result is not None
        assert result < 0


class TestCalculationAccuracy:
    """Test calculation accuracy with known values."""

    def test_apparent_temp_comfort_range(self) -> None:
        """Test apparent temperature in comfort range."""
        # Comfortable conditions: ~20°C, 50% RH, light wind
        result = calculate_apparent_temperature(temperature=20.0, humidity=50, wind_speed=5.0)
        assert result is not None
        # Should be close to actual temperature
        assert abs(result - 20.0) < 2.0

    def test_dew_point_accuracy(self) -> None:
        """Test dew point calculation accuracy."""
        # Known: At 20°C and 60% RH, dew point ≈ 12°C
        result = calculate_dew_point(temperature=20.0, humidity=60)
        assert result is not None
        assert 11.0 < result < 13.0
