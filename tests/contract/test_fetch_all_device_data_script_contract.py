# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract test for the ``fetch_all_device_data.fn`` ReGa bulk-load script.

Guards against re-introducing the empty-value -> ``"0"`` coercion (issue #3228).

A not-yet-measured numeric data point (e.g. ``ACTUAL_TEMPERATURE`` right after a
CCU restart) reports an empty value over the ReGa object model. The script must
SKIP such a data point — leaving it absent from the bulk result, which yields a
cache miss so the value stays unset and ``is_valid`` stays ``False`` — instead of
emitting a literal ``0``. Emitting ``0`` wrote an implausible placeholder that
the integration could not tell apart from a real reading and recorded as
``0 °C``. The script runs on the CCU and cannot be executed in Python, so this
contract pins the source-level invariant.
"""

from pathlib import Path
import re

_SCRIPT = Path(__file__).resolve().parents[2] / "aiohomematic" / "rega_scripts" / "fetch_all_device_data.fn"


def _normalized_source() -> str:
    """Return the script with runs of whitespace collapsed to single spaces."""
    return re.sub(r"\s+", " ", _SCRIPT.read_text(encoding="utf-8"))


class TestFetchAllDeviceDataScript:
    """Contract for the bulk-load script's empty-value handling."""

    def test_empty_numeric_value_is_not_coerced_to_zero(self) -> None:
        """An empty numeric value must not be emitted as ``0`` (#3228)."""
        assert 'if (vDPValue == "") { sValue = "0"' not in _normalized_source()

    def test_empty_numeric_value_is_skipped(self) -> None:
        """An empty numeric value must be skipped via ``bHasValue = false``."""
        assert 'if (vDPValue == "") { bHasValue = false' in _normalized_source()

    def test_script_exists(self) -> None:
        """The bulk-load script ships with the package."""
        assert _SCRIPT.is_file()
