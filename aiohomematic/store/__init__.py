# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Store packages for AioHomematic.

This package groups store implementations used throughout the library:
- persistent: Long-lived on-disk registries for device and paramset descriptions.
- dynamic: Short-lived in-memory caches/trackers for runtime values and connection health.
- visibility: Parameter visibility rules to decide which parameters are relevant.
- patches: Paramset description patching for device-specific corrections.
- storage: Abstraction layer for file persistence with factory pattern.

Package structure
-----------------
- storage.py: Storage abstraction with factory pattern for HA Store integration
- persistent/: DeviceDescriptionRegistry, ParamsetDescriptionRegistry, SessionRecorder
- dynamic/: CommandCache, DeviceDetailsCache, CentralDataCache, PingPongTracker
- visibility/: ParameterVisibilityRegistry
- patches/: ParamsetPatch, ParamsetPatchMatcher for correcting CCU data
- types.py: Shared type definitions (CachedCommand, PongTracker, type aliases)
- serialization.py: Freeze/unfreeze utilities for session recording

"""

from __future__ import annotations

from aiohomematic.store.patches import PARAMSET_PATCHES, ParamsetPatch, ParamsetPatchMatcher
from aiohomematic.store.serialization import cleanup_params_for_session, freeze_params, unfreeze_params
from aiohomematic.store.storage import (
    LocalStorageFactory,
    MigrateFunc,
    Storage,
    StorageError,
    StorageFactoryProtocol,
    StorageProtocol,
)
from aiohomematic.store.types import CacheName, CacheStatistics, IncidentSeverity, IncidentSnapshot, IncidentType

__all__ = [
    # Cache
    "CacheName",
    "CacheStatistics",
    # Incident types
    "IncidentSeverity",
    "IncidentSnapshot",
    "IncidentType",
    # Patches
    "PARAMSET_PATCHES",
    "ParamsetPatch",
    "ParamsetPatchMatcher",
    # Serialization
    "cleanup_params_for_session",
    "freeze_params",
    "unfreeze_params",
    # Storage abstraction
    "LocalStorageFactory",
    "MigrateFunc",
    "Storage",
    "StorageError",
    "StorageFactoryProtocol",
    "StorageProtocol",
]
