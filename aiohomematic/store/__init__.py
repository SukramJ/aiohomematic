# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Store packages for AioHomematic.

This package groups store implementations used throughout the library:
- persistent: Long-lived on-disk caches for device and paramset descriptions.
- dynamic: Short-lived in-memory caches for runtime values and connection health.
- visibility: Parameter visibility rules to decide which parameters are relevant.

Package structure
-----------------
- persistent/: DeviceDescriptionCache, ParamsetDescriptionCache, SessionRecorder
- dynamic/: CommandCache, DeviceDetailsCache, CentralDataCache, PingPongCache
- visibility/: ParameterVisibilityCache
- types.py: Shared type definitions (CachedCommand, PongTracker, type aliases)
- serialization.py: Freeze/unfreeze utilities for session recording

Public API
----------
All cache classes are re-exported from this module for backward compatibility.
Uses lazy imports to avoid circular dependencies with store/types.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohomematic.store.dynamic import CentralDataCache, CommandCache, DeviceDetailsCache, PingPongCache
    from aiohomematic.store.persistent import DeviceDescriptionCache, ParamsetDescriptionCache, SessionRecorder
    from aiohomematic.store.visibility import ParameterVisibilityCache

__all__ = [
    "CentralDataCache",
    "CommandCache",
    "DeviceDescriptionCache",
    "DeviceDetailsCache",
    "ParameterVisibilityCache",
    "ParamsetDescriptionCache",
    "PingPongCache",
    "SessionRecorder",
    "cleanup_files",
    "check_ignore_parameters_is_clean",
]

# Lazy import cache to avoid repeated imports
_import_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:  # kwonly: disable
    """Lazy import of store submodules to avoid circular imports."""
    if name in _import_cache:
        return _import_cache[name]

    if name in ("CentralDataCache", "CommandCache", "DeviceDetailsCache", "PingPongCache"):
        from aiohomematic.store import dynamic  # noqa: PLC0415

        _import_cache["CentralDataCache"] = dynamic.CentralDataCache
        _import_cache["CommandCache"] = dynamic.CommandCache
        _import_cache["DeviceDetailsCache"] = dynamic.DeviceDetailsCache
        _import_cache["PingPongCache"] = dynamic.PingPongCache
        return _import_cache[name]

    if name in ("DeviceDescriptionCache", "ParamsetDescriptionCache", "SessionRecorder", "cleanup_files"):
        from aiohomematic.store import persistent  # noqa: PLC0415

        _import_cache["DeviceDescriptionCache"] = persistent.DeviceDescriptionCache
        _import_cache["ParamsetDescriptionCache"] = persistent.ParamsetDescriptionCache
        _import_cache["SessionRecorder"] = persistent.SessionRecorder
        _import_cache["cleanup_files"] = persistent.cleanup_files
        return _import_cache[name]

    if name in ("ParameterVisibilityCache", "check_ignore_parameters_is_clean"):
        from aiohomematic.store import visibility  # noqa: PLC0415

        _import_cache["ParameterVisibilityCache"] = visibility.ParameterVisibilityCache
        _import_cache["check_ignore_parameters_is_clean"] = visibility.check_ignore_parameters_is_clean
        return _import_cache[name]

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
