# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Paramset description patching system for correcting CCU data.

This package provides a declarative system for patching incorrect paramset
descriptions returned by the CCU. Some devices have firmware bugs or CCU
implementation issues that return wrong MIN/MAX values, incorrect types,
or other malformed parameter metadata.

Package structure
-----------------
- paramset_patches: Declarative patch definitions (ParamsetPatch, PARAMSET_PATCHES)
- matcher: ParamsetPatchMatcher for matching and applying patches

How it works
------------
1. Patches are defined declaratively in paramset_patches.py
2. When fetching paramset descriptions from CCU, the ParamsetPatchMatcher
   checks if any patches apply to the current device/channel/parameter
3. Matching patches are applied, correcting the incorrect values
4. The corrected data is stored in the cache
5. On cache load, data is already patched (no re-patching needed)

Cache strategy
--------------
When the schema version is bumped (to add new patches), the cache is
invalidated and rebuilt from the CCU. This ensures all patches are applied
without complex migration logic.

Adding new patches
------------------
1. Add a new ParamsetPatch entry to PARAMSET_PATCHES in paramset_patches.py
2. Bump SCHEMA_VERSION in ParamsetDescriptionRegistry
3. Include a reason and optionally a ticket reference for traceability

Public API
----------
- ParamsetPatch: Dataclass defining a single patch
- ParamsetPatchMatcher: Matcher for applying patches to paramset descriptions
- PARAMSET_PATCHES: Central registry of all defined patches
"""

from __future__ import annotations

from aiohomematic.store.patches.matcher import ParamsetPatchMatcher
from aiohomematic.store.patches.paramset_patches import PARAMSET_PATCHES, ParamsetPatch

__all__ = [
    "PARAMSET_PATCHES",
    "ParamsetPatch",
    "ParamsetPatchMatcher",
]
