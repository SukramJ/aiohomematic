# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the compat module (JSON abstraction and free-threading detection)."""

from __future__ import annotations

import pytest

from aiohomematic import compat


class TestFreeThreadingDetection:
    """Test free-threading build detection."""

    def test_free_threaded_build_is_bool(self) -> None:
        """FREE_THREADED_BUILD should be a boolean."""
        assert isinstance(compat.FREE_THREADED_BUILD, bool)

    def test_is_free_threaded_build_function(self) -> None:
        """is_free_threaded_build should return a boolean."""
        result = compat.is_free_threaded_build()
        assert isinstance(result, bool)
        # Should match the constant
        assert result == compat.FREE_THREADED_BUILD


class TestOptionFlags:
    """Test option flag constants."""

    def test_option_flags_are_distinct(self) -> None:
        """Option flags should be distinct (bit flags)."""
        flags = [compat.OPT_INDENT_2, compat.OPT_NON_STR_KEYS, compat.OPT_SORT_KEYS]
        # Each flag should be a power of 2
        for flag in flags:
            assert flag > 0
            assert (flag & (flag - 1)) == 0  # Power of 2 check

        # All flags combined should not overlap
        combined = compat.OPT_INDENT_2 | compat.OPT_NON_STR_KEYS | compat.OPT_SORT_KEYS
        assert combined == sum(flags)

    def test_option_flags_are_integers(self) -> None:
        """Option flags should be integers."""
        assert isinstance(compat.OPT_INDENT_2, int)
        assert isinstance(compat.OPT_NON_STR_KEYS, int)
        assert isinstance(compat.OPT_SORT_KEYS, int)


class TestDumps:
    """Test the dumps function."""

    def test_dumps_combined_options(self) -> None:
        """Dumps should accept combined option flags."""
        data = {"z": 1, "a": 2}
        result = compat.dumps(obj=data, option=compat.OPT_SORT_KEYS | compat.OPT_INDENT_2)
        assert isinstance(result, bytes)
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_empty_dict(self) -> None:
        """Dumps should handle empty dict."""
        result = compat.dumps(obj={})
        assert compat.loads(data=result) == {}

    def test_dumps_empty_list(self) -> None:
        """Dumps should handle empty list."""
        result = compat.dumps(obj=[])
        assert compat.loads(data=result) == []

    def test_dumps_nested_structure(self) -> None:
        """Dumps should serialize nested structures."""
        data = {"outer": {"inner": [1, 2, {"deep": True}]}}
        result = compat.dumps(obj=data)
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_simple_dict(self) -> None:
        """Dumps should serialize a simple dict to bytes."""
        data = {"key": "value", "number": 42}
        result = compat.dumps(obj=data)
        assert isinstance(result, bytes)
        # Verify it can be parsed back
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_special_chars(self) -> None:
        """Dumps should handle special characters."""
        data = {"text": 'quotes: " and backslash: \\'}
        result = compat.dumps(obj=data)
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_unicode(self) -> None:
        """Dumps should handle unicode strings."""
        data = {"message": "Hällo Wörld"}
        result = compat.dumps(obj=data)
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_with_list(self) -> None:
        """Dumps should serialize lists."""
        data = [1, 2, 3, "four"]
        result = compat.dumps(obj=data)
        assert isinstance(result, bytes)
        parsed = compat.loads(data=result)
        assert parsed == data

    def test_dumps_with_non_str_keys(self) -> None:
        """Dumps with OPT_NON_STR_KEYS should handle integer keys."""
        data = {1: "one", 2: "two"}
        result = compat.dumps(obj=data, option=compat.OPT_NON_STR_KEYS)
        parsed = compat.loads(data=result)
        # JSON keys are always strings
        assert parsed == {"1": "one", "2": "two"}

    def test_dumps_with_sort_keys(self) -> None:
        """Dumps with OPT_SORT_KEYS should sort keys alphabetically."""
        data = {"z": 1, "a": 2, "m": 3}
        result = compat.dumps(obj=data, option=compat.OPT_SORT_KEYS)
        decoded = result.decode("utf-8")
        # Keys should appear in alphabetical order
        assert decoded.index('"a"') < decoded.index('"m"') < decoded.index('"z"')


class TestLoads:
    """Test the loads function."""

    def test_loads_array(self) -> None:
        """Loads should parse arrays."""
        data = b"[1, 2, 3]"
        result = compat.loads(data=data)
        assert result == [1, 2, 3]

    def test_loads_bytes(self) -> None:
        """Loads should parse bytes."""
        data = b'{"key": "value"}'
        result = compat.loads(data=data)
        assert result == {"key": "value"}

    def test_loads_empty_raises(self) -> None:
        """Loads should raise JSONDecodeError for empty input."""
        with pytest.raises(compat.JSONDecodeError):
            compat.loads(data=b"")

    def test_loads_invalid_json_raises(self) -> None:
        """Loads should raise JSONDecodeError for invalid JSON."""
        with pytest.raises(compat.JSONDecodeError):
            compat.loads(data=b'{"invalid": }')

    def test_loads_string(self) -> None:
        """Loads should parse strings."""
        data = '{"key": "value"}'
        result = compat.loads(data=data)
        assert result == {"key": "value"}

    def test_loads_truncated_raises(self) -> None:
        """Loads should raise JSONDecodeError for truncated JSON."""
        with pytest.raises(compat.JSONDecodeError):
            compat.loads(data=b'{"key": "val')

    def test_loads_unicode_bytes(self) -> None:
        """Loads should handle unicode in bytes."""
        data = '{"msg": "Hällo"}'.encode()
        result = compat.loads(data=data)
        assert result == {"msg": "Hällo"}


class TestJSONDecodeError:
    """Test the JSONDecodeError exception."""

    def test_json_decode_error_can_be_raised(self) -> None:
        """JSONDecodeError should be raisable."""
        with pytest.raises(compat.JSONDecodeError):
            raise compat.JSONDecodeError("test error")

    def test_json_decode_error_from_loads(self) -> None:
        """JSONDecodeError from loads should have a message."""
        with pytest.raises(compat.JSONDecodeError) as exc_info:
            compat.loads(data=b"invalid")
        assert str(exc_info.value)  # Should have an error message

    def test_json_decode_error_is_exception(self) -> None:
        """JSONDecodeError should be an Exception subclass."""
        assert issubclass(compat.JSONDecodeError, Exception)


class TestRoundTrip:
    """Test round-trip serialization/deserialization."""

    @pytest.mark.parametrize(
        "data",
        [
            {"simple": "dict"},
            [1, 2, 3],
            {"nested": {"deep": {"value": 42}}},
            {"mixed": [1, "two", {"three": 3}]},
            {"unicode": "日本語"},
            {"bool": True, "null": None},
            {"float": 3.14159},
            {"negative": -42},
        ],
    )
    def test_round_trip(self, data: object) -> None:
        """Data should survive a dumps/loads round trip."""
        result = compat.loads(data=compat.dumps(obj=data))
        assert result == data
