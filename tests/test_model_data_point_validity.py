"""Test data point validity logic."""

from __future__ import annotations

from unittest.mock import Mock

from aiohomematic.const import ParameterStatus, ParameterType
from aiohomematic.model.data_point import BaseParameterDataPoint


class TestDataPointValidity:
    """Test data point validity checks using simplified mock approach."""

    def test_allows_none_for_action_type(self) -> None:
        """Test that ACTION type allows None."""
        # Create a simple mock that only needs the attributes checked by _allows_none_value
        mock = Mock()
        mock._type = ParameterType.ACTION
        mock._parameter = "PRESS_SHORT"
        mock._special = None

        # Bind the method
        result = BaseParameterDataPoint._allows_none_value(mock)
        assert result is True

    def test_disallows_none_for_float_type(self) -> None:
        """Test that FLOAT type does not allow None by default."""
        mock = Mock()
        mock._type = ParameterType.FLOAT
        mock._parameter = "TEMPERATURE"
        mock._special = None

        result = BaseParameterDataPoint._allows_none_value(mock)
        assert result is False

    def test_enum_invalid_index(self) -> None:
        """Test enum with invalid index."""
        mock = Mock()
        mock._type = ParameterType.ENUM
        mock._values = ("OFF", "AUTO", "MANUAL")
        mock._value = 5  # Out of range

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is False

    def test_enum_invalid_string(self) -> None:
        """Test enum with invalid string value."""
        mock = Mock()
        mock._type = ParameterType.ENUM
        mock._values = ("OFF", "AUTO", "MANUAL")
        mock._value = "INVALID"

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is False

    def test_enum_valid_index(self) -> None:
        """Test enum with valid index."""
        mock = Mock()
        mock._type = ParameterType.ENUM
        mock._values = ("OFF", "AUTO", "MANUAL")
        mock._value = 1  # "AUTO"

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is True

    def test_enum_valid_string(self) -> None:
        """Test enum with valid string value."""
        mock = Mock()
        mock._type = ParameterType.ENUM
        mock._values = ("OFF", "AUTO", "MANUAL")
        mock._value = "AUTO"

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is True

    def test_float_above_max_invalid(self) -> None:
        """Test that float above max is invalid."""
        mock = Mock()
        mock._type = ParameterType.FLOAT
        mock._value = 150.0
        mock._min = 0.0
        mock._max = 100.0
        mock._values = None

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is False

    def test_float_below_min_invalid(self) -> None:
        """Test that float below min is invalid."""
        mock = Mock()
        mock._type = ParameterType.FLOAT
        mock._value = -10.0
        mock._min = 0.0
        mock._max = 100.0
        mock._values = None

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is False

    def test_float_in_range_valid(self) -> None:
        """Test that float within range is valid."""
        mock = Mock()
        mock._type = ParameterType.FLOAT
        mock._value = 50.0
        mock._min = 0.0
        mock._max = 100.0
        mock._values = None

        result = BaseParameterDataPoint.is_value_in_range.__get__(mock)
        assert result is True

    def test_status_none_valid(self) -> None:
        """Test that None status (no STATUS parameter) is valid."""
        mock = Mock()
        mock._status_value = None

        result = BaseParameterDataPoint.is_status_valid.__get__(mock)
        assert result is True

    def test_status_normal_valid(self) -> None:
        """Test that NORMAL status keeps DP valid."""
        mock = Mock()
        mock._status_value = ParameterStatus.NORMAL

        result = BaseParameterDataPoint.is_status_valid.__get__(mock)
        assert result is True

    def test_status_overflow_invalid(self) -> None:
        """Test that OVERFLOW status makes DP invalid."""
        mock = Mock()
        mock._status_value = ParameterStatus.OVERFLOW

        result = BaseParameterDataPoint.is_status_valid.__get__(mock)
        assert result is False
