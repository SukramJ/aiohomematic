# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests that the pytest warning filters still match what they are meant to suppress."""

import inspect
from pathlib import Path
import re
import tomllib

import pydevccu.ccu

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
_THREAD_FILTER = re.compile(r"Exception in thread (\w+):")
_THREAD_NAME = re.compile(r"threading\.Thread\(\s*name=\"(\w+)\"")


def _filtered_thread_names() -> set[str]:
    filters = tomllib.loads(_PYPROJECT.read_text())["tool"]["pytest"]["ini_options"]["filterwarnings"]
    return {match.group(1) for entry in filters if (match := _THREAD_FILTER.search(entry))}


class TestWarningFilters:
    """Test pytest filterwarnings against their sources."""

    def test_thread_filters_name_existing_pydevccu_threads(self) -> None:
        """Every thread-exception filter names a thread pydevccu actually starts."""
        filtered = _filtered_thread_names()
        assert filtered, "no thread-exception filter found in pyproject.toml"
        pydevccu_threads = set(_THREAD_NAME.findall(inspect.getsource(pydevccu.ccu)))
        assert filtered <= pydevccu_threads, f"stale filters: {sorted(filtered - pydevccu_threads)}"
