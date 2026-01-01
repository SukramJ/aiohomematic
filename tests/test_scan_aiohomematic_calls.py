# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic call scanner (script.scan_aiohomematic_calls)."""

from __future__ import annotations

from pathlib import Path

import script.scan_aiohomematic_calls as scanner


class TestShouldIncludeMethod:
    """Test the method filtering logic."""

    def test_excludes_builtins_by_default(self, tmp_path: Path) -> None:
        """Python builtin methods should be excluded by default."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
x = central.device_registry.devices.get("key")
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        method_names = [c.method_name for c in calls]
        # "get" is a builtin dict method
        assert "get" not in method_names

    def test_excludes_constants_by_default(self, tmp_path: Path) -> None:
        """ALL_CAPS names (constants/enums) should be excluded by default."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
x = central.SOME_CONSTANT
y = central.ANOTHER_ONE
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        method_names = [c.method_name for c in calls]
        assert "SOME_CONSTANT" not in method_names
        assert "ANOTHER_ONE" not in method_names

    def test_excludes_private_by_default(self, tmp_path: Path) -> None:
        """Private attributes starting with _ should be excluded by default."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
x = central._private_attr
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        method_names = [c.method_name for c in calls]
        assert "_private_attr" not in method_names

    def test_includes_constants_when_requested(self, tmp_path: Path) -> None:
        """ALL_CAPS names should be included when include_constants=True."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
x = central.SOME_CONSTANT
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p, include_constants=True)
        method_names = [c.method_name for c in calls]
        assert "SOME_CONSTANT" in method_names

    def test_includes_private_when_requested(self, tmp_path: Path) -> None:
        """Private attributes should be included when include_private=True."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
x = central._private_attr
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p, include_private=True)
        method_names = [c.method_name for c in calls]
        assert "_private_attr" in method_names


class TestScanFile:
    """Test file scanning functionality."""

    def test_finds_method_calls(self, tmp_path: Path) -> None:
        """Scanner should find method calls on aiohomematic objects."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
central.start()
central.stop()
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        method_names = [c.method_name for c in calls]
        assert "start" in method_names
        assert "stop" in method_names

    def test_finds_property_access(self, tmp_path: Path) -> None:
        """Scanner should find property access on aiohomematic objects."""
        code = """
from aiohomematic.model.device import Device
device: Device
name = device.name
address = device.device_address
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        method_names = [c.method_name for c in calls]
        assert "name" in method_names
        assert "device_address" in method_names

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Scanner should gracefully handle syntax errors."""
        code = "def broken(\n"
        p = tmp_path / "broken.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        assert calls == []

    def test_infers_class_from_type_hint(self, tmp_path: Path) -> None:
        """Scanner should infer class from type hints."""
        code = """
from aiohomematic.central import CentralUnit
def foo(central: CentralUnit) -> None:
    central.start()
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        assert len(calls) > 0
        call = next(c for c in calls if c.method_name == "start")
        assert call.class_name == "CentralUnit"

    def test_returns_correct_line_numbers(self, tmp_path: Path) -> None:
        """Scanner should return correct line numbers."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
# line 4
central.start()  # line 5
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        call = next(c for c in calls if c.method_name == "start")
        assert call.line_number == 5


class TestScanDirectory:
    """Test directory scanning functionality."""

    def test_ignores_pycache(self, tmp_path: Path) -> None:
        """Scanner should ignore __pycache__ directories."""
        code = """
from aiohomematic.central import CentralUnit
central: CentralUnit
central.start()
"""
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.py").write_text(code, encoding="utf-8")

        calls = scanner.scan_directory(tmp_path)
        assert len(calls) == 0

    def test_scans_multiple_files(self, tmp_path: Path) -> None:
        """Scanner should find calls across multiple files."""
        code1 = """
from aiohomematic.central import CentralUnit
central: CentralUnit
central.start()
"""
        code2 = """
from aiohomematic.model.device import Device
device: Device
device.reload_paramsets()
"""
        (tmp_path / "file1.py").write_text(code1, encoding="utf-8")
        (tmp_path / "file2.py").write_text(code2, encoding="utf-8")

        calls = scanner.scan_directory(tmp_path)
        method_names = [c.method_name for c in calls]
        assert "start" in method_names
        assert "reload_paramsets" in method_names


class TestGroupByClass:
    """Test grouping functionality."""

    def test_groups_methods_by_class(self, tmp_path: Path) -> None:
        """Group methods by their inferred class."""
        code = """
from aiohomematic.central import CentralUnit
from aiohomematic.model.device import Device
central: CentralUnit
device: Device
central.start()
device.reload_paramsets()
"""
        p = tmp_path / "sample.py"
        p.write_text(code, encoding="utf-8")

        calls = scanner.scan_file(p)
        grouped = scanner.group_by_class(calls)

        assert "aiohomematic.central.CentralUnit" in grouped
        assert "aiohomematic.model.device.Device" in grouped
