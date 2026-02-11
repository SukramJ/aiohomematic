# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test parameter inspection, validation, and comparison utilities."""

from __future__ import annotations

import pytest

from aiohomematic.const import Flag, Operations, ParameterData, ParameterType
from aiohomematic.parameter_tools import (
    ParamsetChange,
    ValidationResult,
    coerce_value,
    diff_paramset,
    get_parameter_step,
    has_parameter_events,
    is_parameter_internal,
    is_parameter_readable,
    is_parameter_service,
    is_parameter_visible,
    is_parameter_writable,
    resolve_enum_index,
    resolve_enum_value,
    validate_paramset,
    validate_value,
)

# ---------------------------------------------------------------------------
# Helpers -- reusable ParameterData builders
# ---------------------------------------------------------------------------


def _make_pd(**overrides: object) -> ParameterData:
    """Build a ParameterData dict with overrides."""
    pd: dict[str, object] = {}
    pd.update(overrides)
    return pd  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# ParameterHelper -- flag / operation queries
# ---------------------------------------------------------------------------


class TestIsParameterVisible:
    """Test is_parameter_visible."""

    def test_visible_combined_flags(self) -> None:
        """Test parameter with VISIBLE and other flags combined."""
        pd = _make_pd(FLAGS=Flag.VISIBLE | Flag.INTERNAL)
        assert is_parameter_visible(parameter_data=pd) is True

    def test_visible_flag_not_set(self) -> None:
        """Test parameter without VISIBLE flag."""
        pd = _make_pd(FLAGS=0)
        assert is_parameter_visible(parameter_data=pd) is False

    def test_visible_flag_set(self) -> None:
        """Test parameter with VISIBLE flag."""
        pd = _make_pd(FLAGS=Flag.VISIBLE)
        assert is_parameter_visible(parameter_data=pd) is True

    def test_visible_no_flags_key(self) -> None:
        """Test parameter without FLAGS key defaults to invisible."""
        pd = _make_pd()
        assert is_parameter_visible(parameter_data=pd) is False


class TestIsParameterInternal:
    """Test is_parameter_internal."""

    def test_internal_flag_not_set(self) -> None:
        """Test parameter without INTERNAL flag."""
        pd = _make_pd(FLAGS=Flag.VISIBLE)
        assert is_parameter_internal(parameter_data=pd) is False

    def test_internal_flag_set(self) -> None:
        """Test parameter with INTERNAL flag."""
        pd = _make_pd(FLAGS=Flag.INTERNAL)
        assert is_parameter_internal(parameter_data=pd) is True


class TestIsParameterService:
    """Test is_parameter_service."""

    def test_service_flag_not_set(self) -> None:
        """Test parameter without SERVICE flag."""
        pd = _make_pd(FLAGS=0)
        assert is_parameter_service(parameter_data=pd) is False

    def test_service_flag_set(self) -> None:
        """Test parameter with SERVICE flag."""
        pd = _make_pd(FLAGS=Flag.SERVICE)
        assert is_parameter_service(parameter_data=pd) is True


class TestIsParameterReadable:
    """Test is_parameter_readable."""

    def test_no_operations_key(self) -> None:
        """Test parameter without OPERATIONS key defaults to not readable."""
        pd = _make_pd()
        assert is_parameter_readable(parameter_data=pd) is False

    def test_not_readable(self) -> None:
        """Test parameter without READ operation."""
        pd = _make_pd(OPERATIONS=Operations.WRITE)
        assert is_parameter_readable(parameter_data=pd) is False

    def test_readable(self) -> None:
        """Test parameter with READ operation."""
        pd = _make_pd(OPERATIONS=Operations.READ)
        assert is_parameter_readable(parameter_data=pd) is True

    def test_readable_combined(self) -> None:
        """Test parameter with READ and WRITE operations."""
        pd = _make_pd(OPERATIONS=Operations.READ | Operations.WRITE)
        assert is_parameter_readable(parameter_data=pd) is True


class TestIsParameterWritable:
    """Test is_parameter_writable."""

    def test_not_writable(self) -> None:
        """Test parameter without WRITE operation."""
        pd = _make_pd(OPERATIONS=Operations.READ)
        assert is_parameter_writable(parameter_data=pd) is False

    def test_writable(self) -> None:
        """Test parameter with WRITE operation."""
        pd = _make_pd(OPERATIONS=Operations.WRITE)
        assert is_parameter_writable(parameter_data=pd) is True


class TestHasParameterEvents:
    """Test has_parameter_events."""

    def test_all_operations(self) -> None:
        """Test parameter with all operations."""
        pd = _make_pd(OPERATIONS=Operations.READ | Operations.WRITE | Operations.EVENT)
        assert has_parameter_events(parameter_data=pd) is True

    def test_has_events(self) -> None:
        """Test parameter with EVENT operation."""
        pd = _make_pd(OPERATIONS=Operations.EVENT)
        assert has_parameter_events(parameter_data=pd) is True

    def test_no_events(self) -> None:
        """Test parameter without EVENT operation."""
        pd = _make_pd(OPERATIONS=Operations.READ)
        assert has_parameter_events(parameter_data=pd) is False


# ---------------------------------------------------------------------------
# ParameterHelper -- enum resolution
# ---------------------------------------------------------------------------


class TestResolveEnumValue:
    """Test resolve_enum_value."""

    def test_first_index(self) -> None:
        """Test resolving the first enum index."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON"])
        assert resolve_enum_value(parameter_data=pd, index=0) == "OFF"

    def test_last_index(self) -> None:
        """Test resolving the last enum index."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON", "AUTO"])
        assert resolve_enum_value(parameter_data=pd, index=2) == "AUTO"

    def test_negative_index(self) -> None:
        """Test resolving a negative index."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON"])
        assert resolve_enum_value(parameter_data=pd, index=-1) is None

    def test_no_value_list(self) -> None:
        """Test resolving when VALUE_LIST is missing."""
        pd = _make_pd()
        assert resolve_enum_value(parameter_data=pd, index=0) is None

    def test_out_of_range(self) -> None:
        """Test resolving an out-of-range index."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON"])
        assert resolve_enum_value(parameter_data=pd, index=5) is None

    def test_valid_index(self) -> None:
        """Test resolving a valid enum index."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON", "AUTO"])
        assert resolve_enum_value(parameter_data=pd, index=1) == "ON"


class TestResolveEnumIndex:
    """Test resolve_enum_index."""

    def test_first_value(self) -> None:
        """Test resolving the first enum value."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON"])
        assert resolve_enum_index(parameter_data=pd, value="OFF") == 0

    def test_no_value_list(self) -> None:
        """Test resolving when VALUE_LIST is missing."""
        pd = _make_pd()
        assert resolve_enum_index(parameter_data=pd, value="ON") is None

    def test_unknown_value(self) -> None:
        """Test resolving an unknown enum value."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON"])
        assert resolve_enum_index(parameter_data=pd, value="UNKNOWN") is None

    def test_valid_value(self) -> None:
        """Test resolving a valid enum value."""
        pd = _make_pd(VALUE_LIST=["OFF", "ON", "AUTO"])
        assert resolve_enum_index(parameter_data=pd, value="ON") == 1


# ---------------------------------------------------------------------------
# ParameterHelper -- step size
# ---------------------------------------------------------------------------


class TestGetParameterStep:
    """Test get_parameter_step."""

    def test_bool_returns_none(self) -> None:
        """Test BOOL parameter returns None."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert get_parameter_step(parameter_data=pd) is None

    def test_enum_returns_none(self) -> None:
        """Test ENUM parameter returns None."""
        pd = _make_pd(TYPE=ParameterType.ENUM)
        assert get_parameter_step(parameter_data=pd) is None

    def test_float_boundary_hundred(self) -> None:
        """Test FLOAT parameter with range exactly 100."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=100.0)
        assert get_parameter_step(parameter_data=pd) == 1.0

    def test_float_boundary_seven(self) -> None:
        """Test FLOAT parameter with range exactly 7."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=7.0)
        assert get_parameter_step(parameter_data=pd) == 0.5

    def test_float_large_range(self) -> None:
        """Test FLOAT parameter with range > 100 returns range/100."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=200.0)
        assert get_parameter_step(parameter_data=pd) == 2.0

    def test_float_medium_range(self) -> None:
        """Test FLOAT parameter with range <= 100 returns 1.0."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=50.0)
        assert get_parameter_step(parameter_data=pd) == 1.0

    def test_float_no_min_max(self) -> None:
        """Test FLOAT parameter without MIN/MAX returns 0.5."""
        pd = _make_pd(TYPE=ParameterType.FLOAT)
        assert get_parameter_step(parameter_data=pd) == 0.5

    def test_float_small_range(self) -> None:
        """Test FLOAT parameter with range <= 7 returns 0.5."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=10.0)
        assert get_parameter_step(parameter_data=pd) == 0.5

    def test_integer_always_one(self) -> None:
        """Test INTEGER parameter step is always 1."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        assert get_parameter_step(parameter_data=pd) == 1

    def test_no_type_returns_none(self) -> None:
        """Test parameter without TYPE returns None."""
        pd = _make_pd()
        assert get_parameter_step(parameter_data=pd) is None

    def test_string_returns_none(self) -> None:
        """Test STRING parameter returns None."""
        pd = _make_pd(TYPE=ParameterType.STRING)
        assert get_parameter_step(parameter_data=pd) is None


# ---------------------------------------------------------------------------
# ParameterValidator -- validate_value
# ---------------------------------------------------------------------------


class TestValidateValue:
    """Test validate_value."""

    def test_action_any_value(self) -> None:
        """Test ACTION parameter accepts any value."""
        pd = _make_pd(TYPE=ParameterType.ACTION)
        assert validate_value(parameter_data=pd, value=True).valid is True
        assert validate_value(parameter_data=pd, value="anything").valid is True
        assert validate_value(parameter_data=pd, value=42).valid is True

    def test_bool_invalid(self) -> None:
        """Test BOOL parameter rejects non-boolean values."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        result = validate_value(parameter_data=pd, value=1)
        assert result.valid is False
        assert "bool" in result.reason.lower()

    def test_bool_valid(self) -> None:
        """Test BOOL parameter accepts boolean values."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert validate_value(parameter_data=pd, value=True).valid is True
        assert validate_value(parameter_data=pd, value=False).valid is True

    def test_dummy_type(self) -> None:
        """Test DUMMY parameter accepts any value."""
        pd = _make_pd(TYPE=ParameterType.DUMMY)
        assert validate_value(parameter_data=pd, value="anything").valid is True

    def test_empty_type(self) -> None:
        """Test EMPTY parameter accepts any value."""
        pd = _make_pd(TYPE=ParameterType.EMPTY)
        assert validate_value(parameter_data=pd, value=42).valid is True

    def test_enum_int_without_value_list(self) -> None:
        """Test ENUM parameter with int and no VALUE_LIST is valid."""
        pd = _make_pd(TYPE=ParameterType.ENUM)
        assert validate_value(parameter_data=pd, value=0).valid is True

    def test_enum_invalid_int_index(self) -> None:
        """Test ENUM parameter rejects out-of-range integer index."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"])
        result = validate_value(parameter_data=pd, value=5)
        assert result.valid is False
        assert "out of range" in result.reason.lower()

    def test_enum_invalid_str_value(self) -> None:
        """Test ENUM parameter rejects unknown string value."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"])
        result = validate_value(parameter_data=pd, value="UNKNOWN")
        assert result.valid is False
        assert "VALUE_LIST" in result.reason

    def test_enum_invalid_type(self) -> None:
        """Test ENUM parameter rejects non-int/str values."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"])
        result = validate_value(parameter_data=pd, value=1.5)
        assert result.valid is False

    def test_enum_str_without_value_list(self) -> None:
        """Test ENUM parameter with str and no VALUE_LIST is valid."""
        pd = _make_pd(TYPE=ParameterType.ENUM)
        assert validate_value(parameter_data=pd, value="ON").valid is True

    def test_enum_valid_int_index(self) -> None:
        """Test ENUM parameter accepts valid integer index."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON", "AUTO"])
        assert validate_value(parameter_data=pd, value=0).valid is True
        assert validate_value(parameter_data=pd, value=2).valid is True

    def test_enum_valid_str_value(self) -> None:
        """Test ENUM parameter accepts valid string value."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON", "AUTO"])
        assert validate_value(parameter_data=pd, value="ON").valid is True

    def test_float_accepts_int(self) -> None:
        """Test FLOAT parameter accepts integer values (numeric type)."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=30.0)
        assert validate_value(parameter_data=pd, value=15).valid is True

    def test_float_below_min(self) -> None:
        """Test FLOAT parameter rejects values below minimum."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5)
        result = validate_value(parameter_data=pd, value=4.0)
        assert result.valid is False

    def test_float_valid(self) -> None:
        """Test FLOAT parameter accepts float values within range."""
        pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=30.0)
        assert validate_value(parameter_data=pd, value=21.5).valid is True

    def test_integer_above_max(self) -> None:
        """Test INTEGER parameter rejects values above maximum."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        result = validate_value(parameter_data=pd, value=101)
        assert result.valid is False
        assert "above maximum" in result.reason.lower()

    def test_integer_at_boundaries(self) -> None:
        """Test INTEGER parameter accepts values at boundaries."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        assert validate_value(parameter_data=pd, value=0).valid is True
        assert validate_value(parameter_data=pd, value=100).valid is True

    def test_integer_below_min(self) -> None:
        """Test INTEGER parameter rejects values below minimum."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        result = validate_value(parameter_data=pd, value=-1)
        assert result.valid is False
        assert "below minimum" in result.reason.lower()

    def test_integer_invalid_type(self) -> None:
        """Test INTEGER parameter rejects non-numeric values."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        result = validate_value(parameter_data=pd, value="hello")
        assert result.valid is False
        assert "numeric" in result.reason.lower()

    def test_integer_no_bounds(self) -> None:
        """Test INTEGER parameter without bounds accepts any numeric value."""
        pd = _make_pd(TYPE=ParameterType.INTEGER)
        assert validate_value(parameter_data=pd, value=999999).valid is True

    def test_integer_valid(self) -> None:
        """Test INTEGER parameter accepts integers within range."""
        pd = _make_pd(TYPE=ParameterType.INTEGER, MIN=0, MAX=100)
        assert validate_value(parameter_data=pd, value=50).valid is True

    def test_no_type(self) -> None:
        """Test parameter without TYPE accepts any value."""
        pd = _make_pd()
        assert validate_value(parameter_data=pd, value="anything").valid is True

    def test_string_invalid(self) -> None:
        """Test STRING parameter rejects non-string values."""
        pd = _make_pd(TYPE=ParameterType.STRING)
        result = validate_value(parameter_data=pd, value=42)
        assert result.valid is False
        assert "str" in result.reason.lower()

    def test_string_valid(self) -> None:
        """Test STRING parameter accepts string values."""
        pd = _make_pd(TYPE=ParameterType.STRING)
        assert validate_value(parameter_data=pd, value="hello").valid is True


# ---------------------------------------------------------------------------
# ParameterValidator -- validate_paramset
# ---------------------------------------------------------------------------


class TestValidateParamset:
    """Test validate_paramset."""

    def test_all_valid(self) -> None:
        """Test all valid values return empty dict."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5),
            "MODE": _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"]),
        }
        result = validate_paramset(
            descriptions=descriptions,
            values={"TEMP": 21.0, "MODE": 0},
        )
        assert result == {}

    def test_empty_values(self) -> None:
        """Test empty values dict returns empty result."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5),
        }
        result = validate_paramset(descriptions=descriptions, values={})
        assert result == {}

    def test_multiple_failures(self) -> None:
        """Test multiple failures are all reported."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5),
            "ACTIVE": _make_pd(TYPE=ParameterType.BOOL),
        }
        result = validate_paramset(
            descriptions=descriptions,
            values={"TEMP": 99.0, "ACTIVE": "yes"},
        )
        assert len(result) == 2
        assert "TEMP" in result
        assert "ACTIVE" in result

    def test_some_invalid(self) -> None:
        """Test mixed valid/invalid values return only failures."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5),
            "MODE": _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"]),
        }
        result = validate_paramset(
            descriptions=descriptions,
            values={"TEMP": 99.0, "MODE": 0},
        )
        assert "TEMP" in result
        assert result["TEMP"].valid is False
        assert "MODE" not in result

    def test_unknown_parameter(self) -> None:
        """Test unknown parameter is reported as failure."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5),
        }
        result = validate_paramset(
            descriptions=descriptions,
            values={"TEMP": 21.0, "UNKNOWN_PARAM": 42},
        )
        assert "UNKNOWN_PARAM" in result
        assert "Unknown parameter" in result["UNKNOWN_PARAM"].reason


# ---------------------------------------------------------------------------
# ParameterValidator -- coerce_value
# ---------------------------------------------------------------------------


class TestCoerceValue:
    """Test coerce_value."""

    def test_bool_not_coerced_to_float(self) -> None:
        """Test bool is not coerced to float (bool is subclass of int)."""
        pd = _make_pd(TYPE=ParameterType.FLOAT)
        result = coerce_value(parameter_data=pd, value=True)
        assert result is True

    def test_float_to_int(self) -> None:
        """Test float is coerced to int for INTEGER parameters."""
        pd = _make_pd(TYPE=ParameterType.INTEGER)
        result = coerce_value(parameter_data=pd, value=5.7)
        assert result == 5
        assert isinstance(result, int)

    def test_int_to_float(self) -> None:
        """Test int is coerced to float for FLOAT parameters."""
        pd = _make_pd(TYPE=ParameterType.FLOAT)
        result = coerce_value(parameter_data=pd, value=5)
        assert result == 5.0
        assert isinstance(result, float)

    def test_no_coercion_needed(self) -> None:
        """Test value is returned unchanged when no coercion applies."""
        pd = _make_pd(TYPE=ParameterType.STRING)
        assert coerce_value(parameter_data=pd, value="hello") == "hello"

    def test_no_type(self) -> None:
        """Test value is returned unchanged when no TYPE is set."""
        pd = _make_pd()
        assert coerce_value(parameter_data=pd, value=42) == 42

    def test_str_false_to_bool(self) -> None:
        """Test string 'false' is coerced to False for BOOL parameters."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert coerce_value(parameter_data=pd, value="false") is False

    def test_str_non_bool_unchanged_for_bool(self) -> None:
        """Test non-bool string is not coerced for BOOL parameters."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert coerce_value(parameter_data=pd, value="yes") == "yes"

    def test_str_to_enum_index(self) -> None:
        """Test string is coerced to enum index for ENUM parameters."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON", "AUTO"])
        assert coerce_value(parameter_data=pd, value="ON") == 1

    def test_str_true_case_insensitive(self) -> None:
        """Test string 'True'/'TRUE' is coerced for BOOL parameters."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert coerce_value(parameter_data=pd, value="True") is True
        assert coerce_value(parameter_data=pd, value="TRUE") is True

    def test_str_true_to_bool(self) -> None:
        """Test string 'true' is coerced to True for BOOL parameters."""
        pd = _make_pd(TYPE=ParameterType.BOOL)
        assert coerce_value(parameter_data=pd, value="true") is True

    def test_str_unknown_enum_unchanged(self) -> None:
        """Test unknown enum string value is returned unchanged."""
        pd = _make_pd(TYPE=ParameterType.ENUM, VALUE_LIST=["OFF", "ON"])
        assert coerce_value(parameter_data=pd, value="UNKNOWN") == "UNKNOWN"


# ---------------------------------------------------------------------------
# ParamsetDiff -- diff_paramset
# ---------------------------------------------------------------------------


class TestDiffParamset:
    """Test diff_paramset."""

    def test_empty_paramsets(self) -> None:
        """Test empty paramsets produce empty diff."""
        result = diff_paramset(descriptions={}, baseline={}, current={})
        assert result == {}

    def test_float_type_aware_equality(self) -> None:
        """Test 0.0 and 0 are treated as equal for FLOAT parameters."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"TEMP": 0},
            current={"TEMP": 0.0},
        )
        assert result == {}

    def test_integer_no_type_aware_equality(self) -> None:
        """Test INTEGER parameters use standard equality."""
        descriptions: dict[str, ParameterData] = {
            "COUNT": _make_pd(TYPE=ParameterType.INTEGER),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"COUNT": 5},
            current={"COUNT": 5},
        )
        assert result == {}

    def test_multiple_changes(self) -> None:
        """Test multiple changes are all reported."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT),
            "MODE": _make_pd(TYPE=ParameterType.INTEGER),
            "NAME": _make_pd(TYPE=ParameterType.STRING),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"TEMP": 21.0, "MODE": 1, "NAME": "old"},
            current={"TEMP": 22.0, "MODE": 2, "NAME": "new"},
        )
        assert len(result) == 3

    def test_no_changes(self) -> None:
        """Test identical paramsets produce empty diff."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT),
            "MODE": _make_pd(TYPE=ParameterType.INTEGER),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"TEMP": 21.0, "MODE": 1},
            current={"TEMP": 21.0, "MODE": 1},
        )
        assert result == {}

    def test_only_common_keys(self) -> None:
        """Test only common keys are compared."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT),
            "MODE": _make_pd(TYPE=ParameterType.INTEGER),
            "EXTRA": _make_pd(TYPE=ParameterType.STRING),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"TEMP": 21.0, "MODE": 1},
            current={"TEMP": 22.0, "EXTRA": "new"},
        )
        # Only TEMP is in common -- MODE and EXTRA are not compared
        assert "TEMP" in result
        assert "MODE" not in result
        assert "EXTRA" not in result

    def test_paramset_change_dataclass(self) -> None:
        """Test ParamsetChange is a frozen dataclass."""
        change = ParamsetChange(parameter="TEMP", old_value=21.0, new_value=22.0)
        assert change.parameter == "TEMP"
        assert change.old_value == 21.0
        assert change.new_value == 22.0
        with pytest.raises(AttributeError):
            change.parameter = "other"  # type: ignore[misc]

    def test_unknown_parameter_uses_standard_equality(self) -> None:
        """Test parameter not in descriptions uses standard equality."""
        result = diff_paramset(
            descriptions={},
            baseline={"UNKNOWN": "a"},
            current={"UNKNOWN": "b"},
        )
        assert "UNKNOWN" in result

    def test_value_changed(self) -> None:
        """Test changed value is detected."""
        descriptions: dict[str, ParameterData] = {
            "TEMP": _make_pd(TYPE=ParameterType.FLOAT),
        }
        result = diff_paramset(
            descriptions=descriptions,
            baseline={"TEMP": 21.0},
            current={"TEMP": 22.5},
        )
        assert "TEMP" in result
        assert result["TEMP"].old_value == 21.0
        assert result["TEMP"].new_value == 22.5


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_frozen(self) -> None:
        """Test ValidationResult is frozen."""
        result = ValidationResult(valid=True)
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]

    def test_invalid_result_with_reason(self) -> None:
        """Test invalid result with reason."""
        result = ValidationResult(valid=False, reason="Something went wrong.")
        assert result.valid is False
        assert result.reason == "Something went wrong."

    def test_valid_result(self) -> None:
        """Test valid result defaults."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.reason == ""
