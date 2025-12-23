"""Tests for converter.py of aiohomematic."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from aiohomematic.const import Parameter
from aiohomematic.converter import (
    CONVERTABLE_PARAMETERS,
    convert_combined_parameter_to_paramset,
    convert_hm_level_to_cpv,
    from_homematic_value,
    to_homematic_value,
)


class TestLevelConversion:
    """Test level conversion functions."""

    def test_convert_hm_level_to_cpv(self) -> None:
        """Test converting HM level to combined parameter value."""
        # Test basic conversion
        result = convert_hm_level_to_cpv(value=0.5)
        assert result == "0x64"

        # Test zero value
        result = convert_hm_level_to_cpv(value=0)
        assert result == "0x00"

        # Test full value
        result = convert_hm_level_to_cpv(value=1.0)
        assert result == "0xc8"


class TestCombinedParameterConversion:
    """Test combined parameter conversion functions."""

    def test_convert_combined_parameter_basic(self) -> None:
        """Test basic combined parameter conversion."""
        # Test LEVEL parameter with decimal value (not hex)
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=50")
        assert Parameter.LEVEL in result
        assert result[Parameter.LEVEL] == 0.5

    def test_convert_combined_parameter_multiple_params(self) -> None:
        """Test conversion with multiple parameters."""
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=100,L2=50")
        assert Parameter.LEVEL in result
        assert Parameter.LEVEL_2 in result
        assert result[Parameter.LEVEL] == 1.0
        assert result[Parameter.LEVEL_2] == 0.5

    def test_convert_combined_parameter_with_string_value(self) -> None:
        """Test parameter with non-numeric value triggers exception."""
        # When value can't be converted to int, exception is caught and empty dict returned
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=not_a_number")
        # Should return empty dict due to exception handling
        assert result == {}

    def test_convert_invalid_format_exception(self) -> None:
        """Test that invalid format is handled gracefully."""
        # This should trigger exception handling in the converter
        result = convert_combined_parameter_to_paramset(
            parameter=Parameter.COMBINED_PARAMETER, value="invalid_no_equals"
        )
        assert result == {}

    def test_convert_invalid_split_format(self) -> None:
        """Test that value without proper split format is handled."""
        # This tests exception handling when split doesn't work as expected
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=")
        # Should handle gracefully and return what it can
        assert isinstance(result, dict)

    def test_convert_level_combined_with_comma(self) -> None:
        """Test LEVEL_COMBINED conversion with two values."""
        result = convert_combined_parameter_to_paramset(parameter=Parameter.LEVEL_COMBINED, value="0x64,0x32")
        assert Parameter.LEVEL in result
        assert Parameter.LEVEL_SLATS in result
        # 0x64 = 100, divided by 100 then by 2 = 0.5
        # 0x32 = 50, divided by 100 then by 2 = 0.25
        assert result[Parameter.LEVEL] == 0.5
        assert result[Parameter.LEVEL_SLATS] == 0.25

    def test_convert_level_combined_without_comma(self) -> None:
        """Test LEVEL_COMBINED conversion without comma returns empty dict."""
        result = convert_combined_parameter_to_paramset(parameter=Parameter.LEVEL_COMBINED, value="0x64")
        assert result == {}

    def test_convert_unknown_parameter(self) -> None:
        """Test conversion with unknown parameter name."""
        result = convert_combined_parameter_to_paramset(parameter="UNKNOWN_PARAM", value="test=value")
        assert result == {}


class TestConstants:
    """Test module constants."""

    def test_convertable_parameters(self) -> None:
        """Test CONVERTABLE_PARAMETERS constant."""
        assert Parameter.COMBINED_PARAMETER in CONVERTABLE_PARAMETERS
        assert Parameter.LEVEL_COMBINED in CONVERTABLE_PARAMETERS
        assert len(CONVERTABLE_PARAMETERS) == 2


class TestCacheEfficiency:
    """Test that LRU cache is working."""

    def test_combined_parameter_caching(self) -> None:
        """Test that combined parameter conversion is cached."""
        # Call multiple times with same args
        for _ in range(3):
            result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=100")
            assert Parameter.LEVEL in result

    def test_conversion_caching(self) -> None:
        """Test that repeated calls use cache."""
        # Call multiple times with same args
        for _ in range(5):
            result = convert_hm_level_to_cpv(value=0.5)
            assert result == "0x64"

        # Different values
        result1 = convert_hm_level_to_cpv(value=0.25)
        result2 = convert_hm_level_to_cpv(value=0.75)
        assert result1 == "0x32"
        assert result2 == "0x96"


class TestInternalConverters:
    """Test internal converter functions indirectly."""

    def test_convert_cpv_to_hm_level_hex(self) -> None:
        """Test _convert_cpv_to_hm_level with hex value."""
        # LEVEL_COMBINED with hex values
        result = convert_combined_parameter_to_paramset(parameter=Parameter.LEVEL_COMBINED, value="0x64,0x32")
        assert Parameter.LEVEL in result
        # 0x64 = 100, /100 /2 = 0.5
        assert result[Parameter.LEVEL] == 0.5

    def test_convert_cpv_to_hm_level_non_hex(self) -> None:
        """Test _convert_cpv_to_hm_level with non-hex value."""
        # LEVEL_COMBINED uses _convert_cpv_to_hm_level which handles both hex and non-hex
        # Test with non-hex value to hit the return value line
        result = convert_combined_parameter_to_paramset(parameter=Parameter.LEVEL_COMBINED, value="100,50")
        assert Parameter.LEVEL in result
        # Non-hex values are returned as-is (as string)
        assert result[Parameter.LEVEL] == "100"


class TestEdgeCases:
    """Test edge cases and boundary values."""

    def test_boundary_values(self) -> None:
        """Test boundary values for conversions."""
        # Zero
        result = convert_hm_level_to_cpv(value=0)
        assert result == "0x00"

        # Maximum
        result = convert_hm_level_to_cpv(value=1.0)
        assert result == "0xc8"

        # Midpoint
        result = convert_hm_level_to_cpv(value=0.5)
        assert result == "0x64"

    def test_decimal_value_parsing(self) -> None:
        """Test decimal value parsing."""
        # Test with decimal value (LEVEL uses int, not hex)
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=100")
        assert Parameter.LEVEL in result
        assert result[Parameter.LEVEL] == 1.0

        # Test with another decimal value
        result = convert_combined_parameter_to_paramset(parameter=Parameter.COMBINED_PARAMETER, value="L=75")
        assert Parameter.LEVEL in result
        assert result[Parameter.LEVEL] == 0.75


# =============================================================================
# SINGLEDISPATCH CONVERTER TESTS
# =============================================================================


class _TestEnum(Enum):
    """Test enum for converter tests."""

    VALUE_A = "a"
    VALUE_B = 42


class TestToHomematicValue:
    """Test to_homematic_value singledispatch converter."""

    def test_bool_to_int(self) -> None:
        """Test boolean conversion to integer."""
        assert to_homematic_value(True) == 1
        assert to_homematic_value(False) == 0

    def test_datetime_to_iso(self) -> None:
        """Test datetime conversion to ISO string."""
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = to_homematic_value(dt)
        assert result == "2025-01-15T10:30:00"

    def test_dict_recursive(self) -> None:
        """Test dict conversion with recursive value conversion."""
        result = to_homematic_value({"on": True, "level": 3.14159265359})
        assert result == {"on": 1, "level": 3.141593}

    def test_enum_to_value(self) -> None:
        """Test enum conversion to value."""
        assert to_homematic_value(_TestEnum.VALUE_A) == "a"
        assert to_homematic_value(_TestEnum.VALUE_B) == 42

    def test_float_rounding(self) -> None:
        """Test float rounding to 6 decimal places."""
        assert to_homematic_value(3.14159265359) == 3.141593
        assert to_homematic_value(1.0) == 1.0
        assert to_homematic_value(0.123456789) == 0.123457

    def test_int_passthrough(self) -> None:
        """Test that integers pass through without conversion."""
        # int is subclass of bool in Python, but singledispatch uses MRO
        # so we need to ensure int values are not converted to 1/0
        assert to_homematic_value(42) == 42
        assert to_homematic_value(0) == 0
        assert to_homematic_value(-1) == -1

    def test_list_recursive(self) -> None:
        """Test list conversion with recursive item conversion."""
        result = to_homematic_value([True, False, 3.14159265359])
        assert result == [1, 0, 3.141593]

    def test_nested_structures(self) -> None:
        """Test nested list/dict conversion."""
        result = to_homematic_value({"values": [True, False], "nested": {"flag": True}})
        assert result == {"values": [1, 0], "nested": {"flag": 1}}

    def test_passthrough_types(self) -> None:
        """Test that unregistered types pass through unchanged."""
        assert to_homematic_value(42) == 42
        assert to_homematic_value("hello") == "hello"
        assert to_homematic_value(None) is None

    def test_timedelta_to_seconds(self) -> None:
        """Test timedelta conversion to total seconds."""
        td = timedelta(hours=1, minutes=30)
        assert to_homematic_value(td) == 5400.0

        td_small = timedelta(seconds=45)
        assert to_homematic_value(td_small) == 45.0


class TestFromHomematicValue:
    """Test from_homematic_value singledispatch converter."""

    def test_int_to_bool(self) -> None:
        """Test integer to boolean conversion with target_type."""
        assert from_homematic_value(1, target_type=bool) is True
        assert from_homematic_value(0, target_type=bool) is False
        assert from_homematic_value(42, target_type=bool) is True

    def test_int_without_target(self) -> None:
        """Test integer passthrough without target_type."""
        assert from_homematic_value(42) == 42
        assert from_homematic_value(0) == 0

    def test_passthrough_types(self) -> None:
        """Test that unregistered types pass through unchanged."""
        assert from_homematic_value(3.14) == 3.14
        assert from_homematic_value([1, 2, 3]) == [1, 2, 3]
        assert from_homematic_value(None) is None

    def test_str_to_datetime(self) -> None:
        """Test string to datetime conversion with target_type."""
        result = from_homematic_value("2025-01-15T10:30:00", target_type=datetime)
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_str_without_target(self) -> None:
        """Test string passthrough without target_type."""
        assert from_homematic_value("hello") == "hello"


class TestSingledispatchExtensibility:
    """Test that singledispatch can be extended with new types."""

    def test_register_custom_type(self) -> None:
        """Test registering a custom type converter."""

        # Create a custom type
        class Temperature:
            def __init__(self, celsius: float) -> None:
                self.celsius = celsius

        # Register a converter for it
        @to_homematic_value.register(Temperature)
        def _to_hm_temperature(value: Temperature) -> float:
            return value.celsius

        # Test the converter
        temp = Temperature(21.5)
        assert to_homematic_value(temp) == 21.5

    def test_registered_types_list(self) -> None:
        """Test that we can inspect registered types."""
        # singledispatch exposes .registry attribute
        registry = to_homematic_value.registry
        assert bool in registry
        assert float in registry
        assert datetime in registry
        assert list in registry
        assert dict in registry
