# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Compatibility layer for free-threading support and conditional JSON backend.

This module provides:
- Detection of free-threaded Python builds
- Conditional JSON serialization (orjson for GIL builds, stdlib json for free-threaded)

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import json as _stdlib_json
import sys
import sysconfig
from typing import Any, Final

# =============================================================================
# Free-Threading Detection
# =============================================================================


def is_free_threaded_build() -> bool:
    """
    Return True if Python was built with free-threading support.

    This checks the build configuration, not the runtime GIL state.
    Use this for decisions about which libraries to load.
    """
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def is_gil_enabled() -> bool:
    """
    Return True if the GIL is currently enabled at runtime.

    On standard Python builds, always returns True.
    On free-threaded builds, returns False unless GIL was re-enabled via PYTHON_GIL=1.
    """
    if hasattr(sys, "_is_gil_enabled"):
        return sys._is_gil_enabled()  # pylint: disable=protected-access
    return True  # Standard build - GIL always enabled


# Cache the build type at import time (immutable)
FREE_THREADED_BUILD: Final[bool] = is_free_threaded_build()

# =============================================================================
# Conditional JSON Backend
# =============================================================================

# Try to import orjson, but only use it if NOT in free-threaded mode
_USE_ORJSON: bool = False
_orjson: Any  # Module or None, assigned below

if not FREE_THREADED_BUILD:
    try:
        import orjson as _orjson_module

        _orjson = _orjson_module
        _USE_ORJSON = True
    except ImportError:
        _orjson = None
else:
    _orjson = None


class JSONDecodeError(Exception):
    """Unified JSON decode error that wraps backend-specific errors."""


# Option flags (mirror orjson API, no-op for stdlib json)
OPT_INDENT_2: Final[int] = 1
OPT_NON_STR_KEYS: Final[int] = 2
OPT_SORT_KEYS: Final[int] = 4


def dumps(*, obj: Any, option: int = 0) -> bytes:
    """
    Serialize obj to JSON bytes.

    Args:
        obj: Object to serialize
        option: Bitmask of OPT_* flags (OPT_INDENT_2, OPT_NON_STR_KEYS, OPT_SORT_KEYS)

    Returns:
        JSON as bytes (UTF-8 encoded)

    """
    if _USE_ORJSON and _orjson is not None:
        # Map our option flags to orjson flags
        orjson_opts = 0
        if option & OPT_INDENT_2:
            orjson_opts |= _orjson.OPT_INDENT_2
        if option & OPT_NON_STR_KEYS:
            orjson_opts |= _orjson.OPT_NON_STR_KEYS
        if option & OPT_SORT_KEYS:
            orjson_opts |= _orjson.OPT_SORT_KEYS
        result: bytes = _orjson.dumps(obj, option=orjson_opts)
        return result

    # Stdlib json fallback
    indent = 2 if (option & OPT_INDENT_2) else None
    sort_keys = bool(option & OPT_SORT_KEYS)
    # Note: stdlib json doesn't support non-str keys natively,
    # but we handle this by converting keys to strings
    if option & OPT_NON_STR_KEYS:
        obj = _convert_non_str_keys(obj=obj)
    return _stdlib_json.dumps(obj, indent=indent, sort_keys=sort_keys, ensure_ascii=False).encode("utf-8")


def loads(*, data: bytes | str) -> Any:
    """
    Deserialize JSON bytes/string to Python object.

    Args:
        data: JSON data as bytes or string

    Returns:
        Deserialized Python object

    Raises:
        JSONDecodeError: If data is not valid JSON

    """
    if _USE_ORJSON and _orjson is not None:
        try:
            return _orjson.loads(data)
        except _orjson.JSONDecodeError as exc:
            raise JSONDecodeError(str(exc)) from exc

    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return _stdlib_json.loads(data)
    except _stdlib_json.JSONDecodeError as exc:
        raise JSONDecodeError(str(exc)) from exc


def _convert_non_str_keys(*, obj: Any) -> Any:
    """Recursively convert non-string dict keys to strings for stdlib json."""
    if isinstance(obj, dict):
        return {str(k): _convert_non_str_keys(obj=v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_non_str_keys(obj=item) for item in obj]
    return obj


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Detection
    "FREE_THREADED_BUILD",
    "is_free_threaded_build",
    "is_gil_enabled",
    # JSON API
    "JSONDecodeError",
    "OPT_INDENT_2",
    "OPT_NON_STR_KEYS",
    "OPT_SORT_KEYS",
    "dumps",
    "loads",
]
