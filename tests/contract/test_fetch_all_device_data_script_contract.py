# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract test for the ``fetch_all_device_data.fn`` ReGa bulk-load script (v2.5).

The script runs on the CCU and cannot be executed in Python, so this contract
pins the two source-level invariants that protect against the #3228 placeholder
regression:

1. **VirtualDevices gate** — a data point on the ``VirtualDevices`` interface
   must additionally carry a valid ``LastTimestamp()``. Heating groups expose a
   ``Timestamp()`` right after a CCU restart but no real reading yet; gating on
   ``LastTimestamp()`` keeps them out of the bulk result instead of emitting a
   placeholder ``0``.
2. **Typed empty-value detection** — only a genuine *string* script variable
   (``VarType() == 4``) that is empty is coerced to ``0``. A real numeric ``0``
   has a numeric ``VarType`` and is preserved, so legitimate zero readings are
   no longer conflated with not-yet-measured values (the flaw of the bare
   ``vDPValue == ""`` check, see #3228).
"""

from pathlib import Path
import re

_SCRIPT = Path(__file__).resolve().parents[2] / "aiohomematic" / "rega_scripts" / "fetch_all_device_data.fn"


def _normalized_source() -> str:
    """Return the script with runs of whitespace collapsed to single spaces."""
    return re.sub(r"\s+", " ", _SCRIPT.read_text(encoding="utf-8"))


class TestFetchAllDeviceDataScript:
    """Contract for the bulk-load script's #3228 safeguards."""

    def test_empty_value_detected_via_vartype(self) -> None:
        """An empty value is only coerced to ``0`` for a string script variable (#3228)."""
        source = _normalized_source()
        assert "vDP_Value.VarType()" in source
        assert '(iDP_Value_VarType == 4) && (vDP_Value == "")' in source

    def test_script_exists(self) -> None:
        """The bulk-load script ships with the package."""
        assert _SCRIPT.is_file()

    def test_virtual_devices_require_last_timestamp(self) -> None:
        """VirtualDevices data points must be gated on a valid ``LastTimestamp()`` (#3228)."""
        assert '(!oDP.LastTimestamp()) && (sUse_Interface == "VirtualDevices")' in _normalized_source()
