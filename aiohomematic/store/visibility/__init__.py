# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Parameter visibility rules and cache for Homematic data points.

This package determines which parameters should be created, shown, hidden,
ignored, or un-ignored for channels and devices. It centralizes the rules
that influence the visibility of data points exposed by the library.

Package structure
-----------------
- rules: Static visibility rules (constants, mappings, patterns)
- parser: Un-ignore configuration line parsing
- cache: ParameterVisibilityCache implementation

Public API
----------
- ParameterVisibilityCache: Main visibility decision cache
- check_ignore_parameters_is_clean: Validation helper

Key concepts
------------
- Relevant MASTER parameters: Certain MASTER paramset entries are promoted to
  data points for selected models/channels (e.g. climate related settings), but
  they may still be hidden by default for UI purposes.
- Ignored vs un-ignored: Parameters can be broadly ignored, with exceptions
  defined via explicit un-ignore rules that match model/channel/paramset keys.
- Event suppression: For selected devices, button click events are suppressed
  to avoid noise in event streams.
"""

from __future__ import annotations

from aiohomematic.store.visibility.cache import ParameterVisibilityCache, check_ignore_parameters_is_clean

__all__ = [
    "ParameterVisibilityCache",
    "check_ignore_parameters_is_clean",
]
