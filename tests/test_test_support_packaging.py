# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests that the aiohomematic_test_support wheel ships every data file the package loads."""

from pathlib import Path, PurePosixPath
import tomllib

from aiohomematic_test_support import const

_PACKAGE_DIR = Path(const.__file__).parent


def _package_data_globs() -> list[str]:
    pyproject = tomllib.loads((_PACKAGE_DIR / "pyproject.toml").read_text())
    return pyproject["tool"]["setuptools"]["package-data"]["aiohomematic_test_support"]


def _required_data_files() -> list[str]:
    """Return the data files the package loads, relative to the package directory."""
    files = [f"data/{name}" for name in const.ALL_SESSION_FILES]
    files.append("data/device_translation.json")
    files.extend(
        path.relative_to(_PACKAGE_DIR).as_posix()
        for path in sorted((_PACKAGE_DIR / "data" / "device_descriptions").glob("*.json"))
    )
    return files


class TestTestSupportPackaging:
    """Test the package-data configuration of aiohomematic_test_support."""

    def test_device_descriptions_present(self) -> None:
        assert any(f.startswith("data/device_descriptions/") for f in _required_data_files())

    def test_every_required_data_file_is_packaged(self) -> None:
        globs = _package_data_globs()
        missing = [f for f in _required_data_files() if not any(PurePosixPath(f).full_match(g) for g in globs)]
        assert missing == []
