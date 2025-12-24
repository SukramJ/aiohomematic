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
"""

from __future__ import annotations

from aiohomematic.store.dynamic import CentralDataCache, CommandCache, DeviceDetailsCache, PingPongCache
from aiohomematic.store.persistent import (
    DeviceDescriptionCache,
    ParamsetDescriptionCache,
    SessionRecorder,
    cleanup_files,
)
from aiohomematic.store.visibility import ParameterVisibilityCache, check_ignore_parameters_is_clean

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
