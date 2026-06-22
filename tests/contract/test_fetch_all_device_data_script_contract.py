# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract test for the ``fetch_all_device_data.fn`` ReGa bulk-load script.

The script runs on the CCU and cannot be executed in Python, so this contract
pins source-level invariants of the bulk-load script.
"""

from pathlib import Path
import re

_SCRIPT = Path(__file__).resolve().parents[2] / "aiohomematic" / "rega_scripts" / "fetch_all_device_data.fn"


def _normalized_source() -> str:
    """Return the script with runs of whitespace collapsed to single spaces."""
    return re.sub(r"\s+", " ", _SCRIPT.read_text(encoding="utf-8"))


class TestFetchAllDeviceDataScript:
    """Contract for the bulk-load script."""

    def test_script_exists(self) -> None:
        """The bulk-load script ships with the package."""
        assert _SCRIPT.is_file()
