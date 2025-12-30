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

"""

from __future__ import annotations

from aiohomematic.store.serialization import cleanup_params_for_session, freeze_params, unfreeze_params

__all__ = [
    # Serialization
    "cleanup_params_for_session",
    "freeze_params",
    "unfreeze_params",
]
